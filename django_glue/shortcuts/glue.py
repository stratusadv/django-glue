from typing import Callable, Iterable, Literal, Mapping, Sequence, TypeVar, Union

from django.db.models import Model, QuerySet
from django.forms import BaseForm, BaseFormSet, ModelForm
from django.http import HttpRequest

from django_glue.access import GlueAccess
from django_glue.glue.attributes import DeclaredAttribute
from django_glue.glue.base import BaseGlue
from django_glue.glue.component.object import Component
from django_glue.glue.context import GlueContextManager
from django_glue.glue.function import FunctionGlue
from django_glue.glue.loading import LoadingStrategy
from django_glue.glue.objects.django.computed_attributes import ComputedAttribute
from django_glue.glue.objects.django.form.object import FormGlue
from django_glue.glue.objects.django.formset import FormSetGlue
from django_glue.glue.objects.django.model.object import ModelGlue, RelatedFieldConfig
from django_glue.glue.objects.django.queryset import DEFAULT_BATCH_SIZE, QuerySetGlue
from django_glue.glue.objects.django.template import TemplateGlue
from django_glue.glue.options.django import (
    DEFAULT_SEARCH_LIMIT,
    configure_choices,
)
from django_glue.glue.sequence import SequenceGlue
from django_glue.response import GlueRedirectResponse, GlueResponse


class _GluePropertyDescriptor:
    """
    A descriptor that combines @property with @Glue.attr(required_access=VIEW).

    Usage:
        @Glue.property
        def total_hours(self) -> float:
            return sum(e.hours for e in self.entries)

        @Glue.property(identity=True)
        def date(self) -> datetime.date:
            return self._date

    Properties marked with identity=True are included in the auto-generated
    identity dict and used for reconstructing the Glue object from a policy.
    """

    def __init__(self, func: Callable | None = None, *, identity: bool = False) -> None:
        self._identity = identity
        self._func: Callable | None = None
        self._property: property | None = None
        self._name: str | None = None

        if func is not None:
            self._bind(func)

    def _bind(self, func: Callable) -> '_GluePropertyDescriptor':
        """Bind the function to this descriptor."""
        self._func = func
        self._property = property(func)
        # Attach glue options for GlueAttributeCollector to discover
        from django_glue.glue.attributes.declared import DeclaredAttributeOptions
        self.__glue_options__ = DeclaredAttributeOptions(
            required_access=GlueAccess.VIEW,
            is_callable=False,
            takes_client_state=True,
            updates_client_state=True,
            is_identity=self._identity,
        )
        return self

    def __call__(self, func: Callable) -> '_GluePropertyDescriptor':
        """Support @Glue.property(identity=True) syntax."""
        return self._bind(func)

    def __set_name__(self, owner: type, name: str) -> None:
        self._name = name

    def __get__(self, instance, owner=None):
        if instance is None:
            return self
        if self._property is None:
            raise RuntimeError('GluePropertyDescriptor not properly initialized')
        return self._property.__get__(instance, owner)

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


# Type alias for form parameter: can be either an instance or a class
FormOrClass = Union[ModelForm, type[ModelForm]]
ChoiceSource = TypeVar('ChoiceSource')
TGlue = TypeVar('TGlue', bound=BaseGlue)


class Glue:
    Access = GlueAccess
    Component = Component
    LoadingStrategy = LoadingStrategy
    attribute = DeclaredAttribute
    attr = DeclaredAttribute
    html_attr = _html_attr
    property = _GluePropertyDescriptor
    Response = GlueResponse
    RedirectResponse = GlueRedirectResponse

    @staticmethod
    def choices(
        source: ChoiceSource,
        *,
        search_fields: Sequence[str] = (),
        fields: Sequence[str] = (),
        search_limit: int = DEFAULT_SEARCH_LIMIT,
    ) -> ChoiceSource:
        return configure_choices(
            source=source,
            search_fields=search_fields,
            fields=fields,
            search_limit=search_limit,
        )

    @staticmethod
    def object(
        request: HttpRequest,
        glue: BaseGlue,
    ) -> BaseGlue:
        return GlueContextManager(request).add_glue(glue)

    @staticmethod
    def _configured(request: HttpRequest | None, glue: TGlue) -> TGlue:
        """Register a page-owned object, or return it configured but unbound.

        The family shortcuts serve two contexts. Their established
        request-and-name form registers a page root from a view. Omitting the
        request returns a configured, unbound object for a child property or a
        callable result, where the response pipeline supplies the request and
        the address instead (component-system.md §4).
        """
        if request is None:
            return glue

        return Glue.object(request, glue)

    @staticmethod
    def sequence(
        request: HttpRequest | None = None,
        unique_name: str | None = None,
        items: Iterable[BaseGlue] = (),
        access: GlueAccess = GlueAccess.VIEW,
        loading_strategy: LoadingStrategy = LoadingStrategy.LAZY,
    ) -> SequenceGlue:
        return Glue._configured(request, SequenceGlue(
            list(items),
            name=unique_name,
            access=access,
            loading_strategy=loading_strategy,
        ))

    @staticmethod
    def model(
        request: HttpRequest | None = None,
        unique_name: str | None = None,
        target: Model | None = None,
        access: GlueAccess = GlueAccess.VIEW,
        fields: Sequence[str] | Literal['__all__'] = (),
        exclude: Sequence[str] | Literal['__all__'] = (),
        form: FormOrClass | None = None,
        forms: Mapping[str, FormOrClass] | None = None,
        select_related: Sequence[str] | None = None,
        computed_attributes: Mapping[str, ComputedAttribute] | None = None,
        related_field_config: Mapping[str, RelatedFieldConfig] | None = None,
        loading_strategy: LoadingStrategy = LoadingStrategy.LAZY,
    ) -> ModelGlue:
        return Glue._configured(
            request,
            ModelGlue(
                instance=target,
                name=unique_name,
                access=access,
                fields=fields,
                exclude=exclude,
                form=form,
                forms=forms,
                select_related=select_related,
                computed_attributes=computed_attributes,
                related_field_config=related_field_config,
                loading_strategy=loading_strategy,
            ),
        )

    @staticmethod
    def queryset(
        request: HttpRequest | None = None,
        unique_name: str | None = None,
        target: QuerySet | None = None,
        access: GlueAccess = GlueAccess.VIEW,
        fields: Sequence[str] | Literal['__all__'] = (),
        exclude: Sequence[str] | Literal['__all__'] = (),
        form: FormOrClass | None = None,
        forms: Mapping[str, FormOrClass] | None = None,
        computed_attributes: Mapping[str, ComputedAttribute] | None = None,
        related_field_config: Mapping[str, RelatedFieldConfig] | None = None,
        loading_strategy: LoadingStrategy = LoadingStrategy.LAZY,
        batch_size: int | None | Literal['__default__'] = DEFAULT_BATCH_SIZE,
    ) -> QuerySetGlue:
        return Glue._configured(
            request,
            QuerySetGlue(
                queryset=target,
                name=unique_name,
                access=access,
                fields=fields,
                exclude=exclude,
                form=form,
                forms=forms,
                computed_attributes=computed_attributes,
                related_field_config=related_field_config,
                loading_strategy=loading_strategy,
                batch_size=batch_size,
            ),
        )

    @staticmethod
    def form(
        request: HttpRequest | None = None,
        unique_name: str | None = None,
        target: BaseForm | None = None,
        access: GlueAccess = GlueAccess.CHANGE,
        loading_strategy: LoadingStrategy = LoadingStrategy.LAZY,
    ) -> FormGlue:
        return Glue._configured(
            request,
            FormGlue(
                form=target,
                name=unique_name,
                access=access,
                loading_strategy=loading_strategy,
            ),
        )

    @staticmethod
    def formset(
        request: HttpRequest | None = None,
        unique_name: str | None = None,
        target: BaseFormSet | None = None,
        access: GlueAccess = GlueAccess.CHANGE,
        loading_strategy: LoadingStrategy = LoadingStrategy.EAGER,
    ) -> FormSetGlue:
        return Glue._configured(
            request,
            FormSetGlue(
                formset=target,
                name=unique_name,
                access=access,
                loading_strategy=loading_strategy,
            ),
        )

    @staticmethod
    def template(
        request: HttpRequest,
        unique_name: str,
        target: str,
        initial_context_data: dict | None = None,
        loading_strategy: LoadingStrategy = LoadingStrategy.LAZY,
    ) -> TemplateGlue:
        return Glue.object(
            request=request,
            glue=TemplateGlue(
                target,
                name=unique_name,
                access=GlueAccess.VIEW,
                initial_context_data=initial_context_data,
                loading_strategy=loading_strategy,
            ),
        )

    @staticmethod
    def function(
        request: HttpRequest,
        unique_name: str,
        target: str,
        loading_strategy: LoadingStrategy = LoadingStrategy.LAZY,
    ) -> FunctionGlue:
        return Glue.object(
            request=request,
            glue=FunctionGlue(
                target,
                name=unique_name,
                access=GlueAccess.VIEW,
                loading_strategy=loading_strategy,
            ),
        )
