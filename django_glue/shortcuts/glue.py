import inspect
import warnings
from collections import abc
from dataclasses import replace
from functools import partial, update_wrapper
from typing import Any, Callable, Iterable, Literal, Mapping, TypeVar, Union

from django.db import models
from django.forms import BaseForm, Field, ModelForm
from django.http import HttpRequest

from django_glue.access import GlueAccess
from django_glue.glue.attributes import GlueAttributeDeclaration
from django_glue.glue.attributes.attribute import (
    GlueValueRole,
    _resolve_glue_result_annotation,
    _resolve_result_annotation,
)
from django_glue.glue.attributes.declaration import GlueAttributeDeclarationOptions
from django_glue.glue.attributes.namespace import GlueNamespace
from django_glue.glue.base import BaseGlue
from django_glue.glue.children import glue_child_type_registry
from django_glue.glue.components import Component, ModelAccessMixin, ModelAccessRequiredMixin
from django_glue.glue.event import GlueEvent, emit_event, is_reserved_event_name
from django_glue.glue.context import GlueContextManager, TGlue
from django_glue.glue.function import FunctionGlue
from django_glue.glue.listener import ReceivedEvent, listener
from django_glue.glue.model_parameter import BoundedModelParameter, ConcreteModelParameter
from django_glue.glue.objects.django.computed_attributes import ComputedAttribute
from django_glue.glue.objects.django.form.object import FormGlue
from django_glue.glue.objects.django.formset import FormSetGlue
from django_glue.glue.objects.django.model.object import ModelGlue
from django_glue.glue.objects.django.queryset import DEFAULT_BATCH_SIZE, QuerySetGlue
from django_glue.glue.operation import GlueOperation, GlueOperationKind
from django_glue.glue.sequence import SequenceGlue
from django_glue.glue.options.django import (
    DEFAULT_SEARCH_LIMIT,
    configure_choices,
)
from django_glue.response import GlueRedirectResponse, GlueResponse


class _GluePropertyDescriptor:
    """
    A descriptor that combines @property with @Glue.attr(required_access=VIEW).

    Usage:
        @Glue.property
        def total_hours(self) -> float:
            return sum(e.hours for e in self.entries)
    """

    def __init__(self, func: Callable) -> None:
        self._func = func
        self._property = property(func)
        self._name: str | None = None
        expected_type, is_nullable = _resolve_glue_result_annotation(func)
        self.__glue_options__ = GlueAttributeDeclarationOptions(
            required_access=GlueAccess.VIEW,
            is_callable=False,
            value_role=GlueValueRole.DERIVED_OUTPUT,
            expected_type=expected_type,
            is_nullable=is_nullable,
        )
        if expected_type is not None and type(self) is _GluePropertyDescriptor:
            warnings.warn(
                f'Glue.property on {func.__qualname__}() declares a child Glue object. Declare a '
                'child with Glue.child; Glue.property will only compute values in django-glue 2.0.',
                DeprecationWarning,
                stacklevel=2,
            )

    def __set_name__(self, owner: type, name: str) -> None:
        self._name = name

    def __get__(self, instance, owner=None):
        if instance is None:
            return self
        return self._property.__get__(instance, owner)


class _GlueChildDescriptor(_GluePropertyDescriptor):
    """
    A child its owner declares: an island with its own token and access. The
    decorated method initializes it, and its return annotation names what it
    returns: a Django type a Glue object is registered for, such as a form
    class, or a Glue object.

    See ``Glue.child`` for declaring and reading one.
    """

    def __init__(self, func: Callable, /, **options: Any) -> None:
        super().__init__(func)
        expected_type = self.__glue_options__.expected_type
        is_nullable = self.__glue_options__.is_nullable
        if expected_type is None:
            value_type, is_nullable = _resolve_result_annotation(func)
            child_type = glue_child_type_registry.for_value_type(value_type)
            if child_type is None:
                msg = (
                    f'Glue.child {func.__qualname__}() needs a return annotation naming a Django '
                    'type a Glue object is registered for, such as a form class, or a Glue object, '
                    'such as -> Glue.Form.'
                )
                raise TypeError(msg)
            expected_type = child_type.glue_class
        else:
            child_type = glue_child_type_registry.for_glue_class(expected_type)

        if options:
            if child_type is None:
                msg = (
                    f'Glue.child {func.__qualname__}() returns a {expected_type.__qualname__}, '
                    'which takes no options from @Glue.child.'
                )
                raise TypeError(msg)
            child_type.check_options(options, child=func.__qualname__)

        self._options = options
        self.__glue_options__ = replace(
            self.__glue_options__,
            expected_type=expected_type,
            is_nullable=is_nullable,
            is_declared_child=True,
            getter=self._glue_object,
        )

    def __get__(self, instance, owner=None):
        if instance is None:
            return self
        glue_object = self._glue_object(instance)
        if glue_object is None:
            return None
        child_type = glue_child_type_registry.for_glue_class(type(glue_object))
        return glue_object if child_type is None else child_type.read(glue_object)

    def _glue_object(self, instance: Any) -> BaseGlue | None:
        """The child's Glue object, which Glue reads where application code reads the child's value."""
        if not isinstance(instance, Component):
            return self._initialize(instance)
        submitted = instance._submitted_child(self._name)
        if submitted is not None:
            return submitted
        # Built by its initializer once per request: a component lives for one request (ADR 049).
        initialized = instance.__dict__.setdefault('_initialized_children', {})
        if self._name not in initialized:
            initialized[self._name] = self._initialize(instance)
        return initialized[self._name]

    def _initialize(self, instance: Any) -> BaseGlue | None:
        """
        The Glue object the decorated method creates: the one it returns, or the
        Django value it returns wrapped in its registered Glue object, with the
        decorator's options and, by default, its owner's access (ADR 050).
        """
        value = self._func(instance)
        if value is None:
            return None
        if isinstance(value, BaseGlue):
            if self._options:
                msg = (
                    f'Glue.child {self._func.__qualname__}() returned a Glue object under '
                    'options of its own: a setting has one place. Give the options to the Glue '
                    'object, or return the Django value it wraps.'
                )
                raise TypeError(msg)
            return value

        child_type = glue_child_type_registry.for_value_type(type(value))
        if child_type is None:
            msg = (
                f'Glue.child {self._func.__qualname__}() returned a {type(value).__qualname__}, '
                'which no Glue object is registered for. Return a Glue object or a Django value '
                'a Glue object wraps, such as a form.'
            )
            raise TypeError(msg)
        return child_type.wrap(value, name=self._name, **{'access': instance.access, **self._options})


def _child(func: Callable | None = None, /, **options: Any) -> Any:
    """
    Declares a child: an island with its own signed token, access and calls.
    Written bare or with the options of the Glue object its return annotation
    is registered with. A method that returns a Django form is wrapped in a
    ``FormGlue`` under the child's name, which takes ``access`` and
    ``editable``; with no ``access`` it has its owner's (ADR 050):

        @Glue.child(access=Glue.Access.CHANGE)
        def filters(self) -> JournalEntryFilterForm:
            return JournalEntryFilterForm(company=self.request.company)

    A method may instead return a Glue object, such as ``Glue.form(...)``,
    which keeps its own options and access; it is then declared with no
    options of its own.

    Reading a form child returns the Django form, however it was declared:
    bound to the values the browser submitted or, with nothing submitted, to
    its initial values, and validated only when asked. Its errors reach the
    browser as a ``validate()`` call's do. On a ``Glue.Component``, a child
    the user may change is submitted with every call, refresh and re-render,
    so one call can validate several children together:

        @Glue.attr(required_access=Glue.Access.ADD)
        def send(self) -> None:
            if self.header.is_valid():
                ...

    A child with VIEW access is never submitted.
    """
    if func is None:
        return partial(_GlueChildDescriptor, **options)
    return _GlueChildDescriptor(func, **options)


def _attr(*args: Any, **kwargs: Any) -> Any:
    return GlueAttributeDeclaration(*args, **kwargs)


_attr = update_wrapper(
    _attr,
    GlueAttributeDeclaration,
    assigned=('__module__', '__name__', '__qualname__', '__doc__'),
    updated=(),
)


def _html_attr(*args, **kwargs) -> GlueAttributeDeclaration:
    """
    Shortcut for @Glue.attr(render_as_html=True).

    Use on a `@Glue.attr`-style method that returns a TemplateResponse when
    it should be coerced to a GlueTemplateResponse (rendered HTML, chainable
    on the client via .renderInnerHtml(...)) instead of the default of
    sending the TemplateResponse's rendered text as plain result data.

    Usage:
        @Glue.html_attr
        def render_panel(self, request: HttpRequest) -> TemplateResponse:
            ...

        @Glue.html_attr(required_access=GlueAccess.CHANGE)
        def render_editable_panel(self, request: HttpRequest) -> TemplateResponse:
            ...
    """
    kwargs.setdefault('render_as_html', True)
    return GlueAttributeDeclaration(*args, **kwargs)


def _component_parameter(*args: Any, **kwargs: Any) -> GlueAttributeDeclaration:
    """
    Shortcut for @Glue.attr(parameter=True).

    Marks a declared value as a component construction parameter so it is
    collected by ``Component._declared_parameters`` and supplied at component
    construction time. The value role is set independently, as with
    ``Glue.attr``:

        class MyComponent(Glue.Component):
            date = Glue.ComponentParameter()                      # reconstructor
            note = Glue.ComponentParameter('', editable=True)     # editable state

    Decorating a method declares a model parameter whose method initializes the
    row from its primary key (ADR 021):

        @Glue.ComponentParameter
        def entry(self, pk: int) -> TimeEntry:
            return TimeEntry.objects.get(pk=pk, user=self.request.user)

    An initializer that also takes the model accepts a row of any concrete
    subclass of its return annotation (ADR 026):

        @Glue.ComponentParameter
        def host(self, model: type[CommentHost], pk: int) -> CommentHost:
            return model._default_manager.get(pk=pk)
    """
    if len(args) == 1 and not kwargs and inspect.isfunction(args[0]):
        if len(inspect.signature(args[0]).parameters) == BoundedModelParameter.initializer_arity:
            return BoundedModelParameter(args[0])
        return ConcreteModelParameter(args[0])
    kwargs.setdefault('parameter', True)
    return GlueAttributeDeclaration(*args, **kwargs)


def _session_attr(*args: Any, **kwargs: Any) -> GlueAttributeDeclaration:
    """
    Shortcut for Glue.attr(session=True).

    Keeps a component's declared value in its session (ADR 031) instead of in
    the signed token, so it survives a page load and is shared by every
    instance of the class within one user's session. The client reads it and
    cannot write it; a callable changes it by assignment:

        class OnboardingComponent(Glue.Component):
            step: int = Glue.SessionAttr(0)

            @Glue.attr(required_access=Glue.Access.CHANGE)
            def advance(self) -> None:
                self.step += 1
    """
    kwargs.setdefault('session', True)
    return GlueAttributeDeclaration(*args, **kwargs)


class _ComponentFieldDeclaration(GlueAttributeDeclaration):
    """A ``Glue.ComponentField`` declaration, which only a component may hold."""

    def __set_name__(self, owner: type, name: str) -> None:
        super().__set_name__(owner, name)
        if not (isinstance(owner, type) and issubclass(owner, Component)):
            msg = (
                f"Glue.ComponentField on {owner.__name__}.{name} declares a Glue.Component's "
                f'value; {owner.__name__!r} is not a Component.'
            )
            raise TypeError(msg)


def _component_field(field: Field) -> Any:
    """
    A component value a Django form field holds (ADR 051). The field says all of it: its
    ``initial`` is the value's default, called when it is a callable; it is editable unless
    it is ``disabled``; and it cleans what the browser sends and describes the value to it.
    It returns ``Any``, as ``Glue.attr`` does, so the attribute can be hinted with the type
    the field cleans to; the field, not the hint, checks and converts the value:

        class CustomerListComponent(Glue.Component):
            sort: NameSortChoices = Glue.ComponentField(forms.TypedChoiceField(
                choices=NameSortChoices.choices,
                coerce=NameSortChoices,
                initial=NameSortChoices.NAME,
            ))

    A required field with no ``initial`` is refused: the value would start as one the field
    refuses.
    """
    if not isinstance(field, Field):
        msg = f'Glue.ComponentField() takes a Django form field, not {type(field).__name__}.'
        raise TypeError(msg)
    if field.required and field.initial is None:
        msg = (
            f'Glue.ComponentField({type(field).__name__}) is required, so it needs an initial to '
            'start from; or make it required=False.'
        )
        raise TypeError(msg)

    starting = {'default_factory': field.initial} if callable(field.initial) else {'default': field.initial}
    return _ComponentFieldDeclaration(editable=not field.disabled, value_type=field, **starting)


def _event(obj: Any | None = None, name: str | None = None, payload: dict[str, Any] | None = None) -> GlueEvent | None:
    """
    ``Glue.event()`` with no arguments returns a ``GlueEvent`` descriptor for
    class-body use (``saved = Glue.event()``). Called with a Glue object it
    fires a named event on that object inline — ``Glue.event(self, 'saved',
    {'pk': 1})`` — the counterpart to the declared-event callable, landing in
    the same ``effects.events`` channel as ``self.saved(pk=1)``.
    """
    if obj is None:
        return GlueEvent()
    if not isinstance(name, str) or not name or is_reserved_event_name(name):
        msg = (
            f'Glue event {name!r} must be a non-empty name that does not '
            'conflict with a browser event or reserved name.'
        )
        raise ValueError(msg)
    emit_event(obj, name, payload if payload is not None else {})


# Type alias for form parameter: can be either an instance or a class
FormOrClass = Union[ModelForm, type[ModelForm]]
ChoiceSource = TypeVar('ChoiceSource')


class Glue:
    Access = GlueAccess
    Component = Component
    ModelAccessMixin = ModelAccessMixin
    ModelAccessRequiredMixin = ModelAccessRequiredMixin
    Form = FormGlue
    FormSet = FormSetGlue
    Model = ModelGlue
    QuerySet = QuerySetGlue
    Sequence = SequenceGlue
    Operation = GlueOperation
    OperationKind = GlueOperationKind
    attribute = _attr
    attr = _attr
    ComponentParameter = _component_parameter
    SessionAttr = _session_attr
    ComponentField = _component_field
    event = _event
    listener = staticmethod(listener)
    ReceivedEvent = ReceivedEvent
    html_attr = _html_attr
    namespace = GlueNamespace
    property = _GluePropertyDescriptor
    child = _child
    Response = GlueResponse
    RedirectResponse = GlueRedirectResponse

    @staticmethod
    def fields(*paths: str, **relations: abc.Sequence[str]) -> tuple[str, ...]:
        """Build a field selection from leaf names and per-relation subfields,
        normalized to the canonical ``relation__leaf`` paths ``fields`` and
        ``exclude`` already accept (state-model.md §9). Nest a ``Glue.fields()``
        result as a relation's value for deeper projections."""
        selection: list[str] = []
        for path in paths:
            if not isinstance(path, str) or not path:
                msg = 'Glue.fields paths must be non-empty strings.'
                raise TypeError(msg)
            selection.append(path)
        for relation_name, subpaths in relations.items():
            if isinstance(subpaths, str) or not subpaths:
                msg = (
                    f'Glue.fields({relation_name}=...) must be a non-empty sequence '
                    'of subfield names, not a string.'
                )
                raise TypeError(msg)
            for subpath in subpaths:
                if not isinstance(subpath, str) or not subpath:
                    msg = f'Glue.fields({relation_name}=...) subfields must be non-empty strings.'
                    raise TypeError(msg)
                selection.append(f'{relation_name}__{subpath}')
        return tuple(dict.fromkeys(selection))

    @staticmethod
    def choices(
        source: ChoiceSource,
        *,
        search_fields: abc.Sequence[str] = (),
        fields: abc.Sequence[str] = (),
        search_limit: int = DEFAULT_SEARCH_LIMIT,
        label_formatter: Callable | str | None = None,
    ) -> ChoiceSource:
        return configure_choices(
            source=source,
            search_fields=search_fields,
            fields=fields,
            search_limit=search_limit,
            label_formatter=label_formatter,
        )

    @staticmethod
    def object(
        request: HttpRequest,
        glue: TGlue,
    ) -> TGlue:
        return Glue._add_to_context(
            request,
            glue,
        )

    @staticmethod
    def _add_to_context(
        request: HttpRequest | None,
        glue: TGlue,
    ) -> TGlue:
        if request is None:
            return glue
        return GlueContextManager(request).add_glue(glue)

    @staticmethod
    def model(
        request: HttpRequest | None = None,
        unique_name: str | None = None,
        target: models.Model | None = None,
        access: GlueAccess = GlueAccess.VIEW,
        *,
        fields: abc.Sequence[str] | Literal['__all__'] = (),
        exclude: abc.Sequence[str] | Literal['__all__'] = (),
        editable: abc.Sequence[str] | None = None,
        form: FormOrClass | None = None,
        forms: Mapping[str, FormOrClass] | None = None,
        select_related: abc.Sequence[str] | None = None,
        computed_attributes: Mapping[str, ComputedAttribute] | None = None,
        choices: Mapping[str, models.QuerySet] | None = None,
    ) -> ModelGlue:
        glue_object = ModelGlue(
            instance=target,
            name=unique_name,
            access=access,
            fields=fields,
            exclude=exclude,
            editable=editable,
            form=form,
            forms=forms,
            select_related=select_related,
            computed_attributes=computed_attributes,
            choices=choices,
        )
        return Glue._add_to_context(
            request,
            glue_object,
        )

    @staticmethod
    def queryset(
        request: HttpRequest | None = None,
        unique_name: str | None = None,
        target: models.QuerySet | None = None,
        access: GlueAccess = GlueAccess.VIEW,
        *,
        fields: abc.Sequence[str] | Literal['__all__'] = (),
        exclude: abc.Sequence[str] | Literal['__all__'] = (),
        editable: abc.Sequence[str] | None = None,
        filters: Mapping[str, abc.Sequence[str]] | None = None,
        ordering: abc.Sequence[str] | None = None,
        form: FormOrClass | None = None,
        forms: Mapping[str, FormOrClass] | None = None,
        computed_attributes: Mapping[str, ComputedAttribute] | None = None,
        choices: Mapping[str, models.QuerySet] | None = None,
        batch_size: int | None | Literal['__default__'] = DEFAULT_BATCH_SIZE,
    ) -> QuerySetGlue:
        glue_object = QuerySetGlue(
            queryset=target,
            name=unique_name,
            access=access,
            fields=fields,
            exclude=exclude,
            editable=editable,
            filters=filters,
            ordering=ordering,
            form=form,
            forms=forms,
            computed_attributes=computed_attributes,
            choices=choices,
            batch_size=batch_size,
        )
        return Glue._add_to_context(
            request,
            glue_object,
        )

    @staticmethod
    def form(
        request: HttpRequest | None = None,
        unique_name: str | None = None,
        target: BaseForm | None = None,
        access: GlueAccess = GlueAccess.CHANGE,
        *,
        editable: abc.Sequence[str] | None = None,
        form_kwargs: Mapping[str, Any] | None = None,
    ) -> FormGlue:
        glue_object = FormGlue(
            form=target,
            name=unique_name,
            access=access,
            editable=editable,
            form_kwargs=form_kwargs,
        )
        return Glue._add_to_context(
            request,
            glue_object,
        )

    @staticmethod
    def formset(
        request: HttpRequest | None = None,
        unique_name: str | None = None,
        target: type[FormSetGlue] | type[BaseForm] | None = None,
        access: GlueAccess = GlueAccess.CHANGE,
        *,
        initial: Iterable[Mapping[str, Any]] = (),
        instances: Iterable[models.Model | BaseForm] = (),
        new_row_defaults: Mapping[str, Any] | None = None,
        form_kwargs: Mapping[str, Any] | None = None,
        min_num: int | None = None,
        max_num: int | None = None,
        can_delete: bool | None = None,
        extra: int | None = None,
    ) -> FormSetGlue:
        if isinstance(target, type) and issubclass(target, FormSetGlue):
            glue_object = target(
                initial=initial,
                instances=instances,
                new_row_defaults=new_row_defaults,
                form_kwargs=form_kwargs,
                name=unique_name,
                access=access,
                min_num=min_num,
                max_num=max_num,
                can_delete=can_delete,
                extra=extra,
            )
        else:
            if not (isinstance(target, type) and issubclass(target, BaseForm)):
                msg = (
                    f'Glue.formset() takes a form class or a Glue.FormSet subclass, not '
                    f'{target!r}. The formset is rebuilt from importable classes on every '
                    'request, so a Django formset or formset_factory() class cannot be glued: '
                    'declare a Glue.FormSet subclass with form_class, min_num, max_num and '
                    'can_delete instead.'
                )
                raise TypeError(msg)
            glue_object = FormSetGlue(
                target,
                initial=initial,
                instances=instances,
                new_row_defaults=new_row_defaults,
                form_kwargs=form_kwargs,
                name=unique_name,
                access=access,
                min_num=min_num,
                max_num=max_num,
                can_delete=can_delete,
                extra=extra,
            )
        return Glue._add_to_context(
            request,
            glue_object,
        )

    @staticmethod
    def function(
        request: HttpRequest,
        unique_name: str,
        target: str,
    ) -> FunctionGlue:
        return Glue.object(
            request=request,
            glue=FunctionGlue(
                target,
                name=unique_name,
                access=GlueAccess.VIEW,
            ),
        )
