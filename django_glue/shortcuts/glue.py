from functools import update_wrapper
from typing import Any, Callable, Literal, Mapping, Sequence, TypeVar, Union

from django.db.models import Model, QuerySet
from django.forms import BaseForm, ModelForm
from django.http import HttpRequest

from django_glue.access import GlueAccess
from django_glue.glue.attributes import DeclaredAttribute
from django_glue.glue.attributes.declared import DeclaredAttributeOptions
from django_glue.glue.attributes.definition import (
    GlueValueRole,
    _resolve_glue_result_annotation,
)
from django_glue.glue.attributes.namespace import GlueNamespace
from django_glue.glue.component import Component
from django_glue.glue.event import GlueEvent, emit_event, is_reserved_event_name
from django_glue.glue.context import GlueContextManager, TGlue
from django_glue.glue.function import FunctionGlue
from django_glue.glue.objects.django.computed_attributes import ComputedAttribute
from django_glue.glue.objects.django.form.object import FormGlue
from django_glue.glue.objects.django.formset import FormSetGlue
from django_glue.glue.objects.django.model.object import ModelGlue
from django_glue.glue.objects.django.queryset import DEFAULT_BATCH_SIZE, QuerySetGlue
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
        self.__glue_options__ = DeclaredAttributeOptions(
            required_access=GlueAccess.VIEW,
            is_callable=False,
            value_role=GlueValueRole.DERIVED_OUTPUT,
            expected_type=expected_type,
            is_nullable=is_nullable,
        )

    def __set_name__(self, owner: type, name: str) -> None:
        self._name = name

    def __get__(self, instance, owner=None):
        if instance is None:
            return self
        return self._property.__get__(instance, owner)

def _attr(*args: Any, **kwargs: Any) -> Any:
    return DeclaredAttribute(*args, **kwargs)


_attr = update_wrapper(
    _attr,
    DeclaredAttribute,
    assigned=('__module__', '__name__', '__qualname__', '__doc__'),
    updated=(),
)


def _html_attr(*args, **kwargs) -> DeclaredAttribute:
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
    return DeclaredAttribute(*args, **kwargs)


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
    FormSet = FormSetGlue
    attribute = _attr
    attr = _attr
    event = _event
    html_attr = _html_attr
    namespace = GlueNamespace
    property = _GluePropertyDescriptor
    Response = GlueResponse
    RedirectResponse = GlueRedirectResponse

    @staticmethod
    def fields(*paths: str, **relations: Sequence[str]) -> tuple[str, ...]:
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
        search_fields: Sequence[str] = (),
        fields: Sequence[str] = (),
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
        target: Model | None = None,
        access: GlueAccess = GlueAccess.VIEW,
        *,
        fields: Sequence[str] | Literal['__all__'] = (),
        exclude: Sequence[str] | Literal['__all__'] = (),
        editable: Sequence[str] | None = None,
        form: FormOrClass | None = None,
        forms: Mapping[str, FormOrClass] | None = None,
        select_related: Sequence[str] | None = None,
        computed_attributes: Mapping[str, ComputedAttribute] | None = None,
        choices: Mapping[str, QuerySet] | None = None,
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
        target: QuerySet | None = None,
        access: GlueAccess = GlueAccess.VIEW,
        *,
        fields: Sequence[str] | Literal['__all__'] = (),
        exclude: Sequence[str] | Literal['__all__'] = (),
        editable: Sequence[str] | None = None,
        form: FormOrClass | None = None,
        forms: Mapping[str, FormOrClass] | None = None,
        computed_attributes: Mapping[str, ComputedAttribute] | None = None,
        choices: Mapping[str, QuerySet] | None = None,
        batch_size: int | None | Literal['__default__'] = DEFAULT_BATCH_SIZE,
    ) -> QuerySetGlue:
        glue_object = QuerySetGlue(
            queryset=target,
            name=unique_name,
            access=access,
            fields=fields,
            exclude=exclude,
            editable=editable,
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
        editable: Sequence[str] | None = None,
    ) -> FormGlue:
        glue_object = FormGlue(
            form=target,
            name=unique_name,
            access=access,
            editable=editable,
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
        min_num: int | None = None,
        max_num: int | None = None,
        can_delete: bool | None = None,
    ) -> FormSetGlue:
        if isinstance(target, type) and issubclass(target, FormSetGlue):
            glue_object = target(
                name=unique_name,
                access=access,
                min_num=min_num,
                max_num=max_num,
                can_delete=can_delete,
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
                name=unique_name,
                access=access,
                min_num=min_num,
                max_num=max_num,
                can_delete=can_delete,
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
