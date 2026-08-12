from typing import Callable, Iterable, Literal, Mapping, Sequence, Union

from django.db.models import Model, QuerySet
from django.forms import BaseForm, ModelForm
from django.http import HttpRequest

from django_glue.access import GlueAccess
from django_glue.glue.base import BaseGlue
from django_glue.glue.collection import CollectionGlue
from django_glue.glue.context import GlueContextManager
from django_glue.glue.loading import LoadingStrategy
from django_glue.glue.objects.django.form.object import FormGlue
from django_glue.glue.objects.django.computed_attributes import ComputedAttribute
from django_glue.glue.objects.django.model.object import ModelGlue
from django_glue.glue.objects.django.queryset import QuerySetGlue
from django_glue.glue.objects.django.template import TemplateGlue
from django_glue.glue.function import FunctionGlue
from django_glue.glue.json import JsonGlue, JsonValue
from django_glue.glue.attributes import DeclaredAttribute
from django_glue.response import GlueRedirectResponse, GlueResponse


class _GluePropertyDescriptor:
    """
    A descriptor that combines @property with @Glue.attribute(access=VIEW).

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
            access=GlueAccess.VIEW,
            is_callable=False,
            loads_state=True,
            updates_state=True,
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

# Type alias for form parameter: can be either an instance or a class
FormOrClass = Union[ModelForm, type[ModelForm]]


class Glue:
    Access = GlueAccess
    LoadingStrategy = LoadingStrategy
    attribute = DeclaredAttribute
    property = _GluePropertyDescriptor
    Response = GlueResponse
    RedirectResponse = GlueRedirectResponse

    @staticmethod
    def object(
        request: HttpRequest,
        glue: BaseGlue,
    ) -> BaseGlue:
        return GlueContextManager(request).add_glue(glue)

    @staticmethod
    def collection(
        request: HttpRequest,
        unique_name: str,
        items: Iterable[BaseGlue],
        access: GlueAccess = GlueAccess.VIEW,
        loading_strategy: LoadingStrategy = LoadingStrategy.LAZY,
    ) -> CollectionGlue:
        return Glue.object(request, CollectionGlue(
            list(items),
            name=unique_name,
            access=access,
            loading_strategy=loading_strategy,
        ))

    @staticmethod
    def model(
        request: HttpRequest,
        unique_name: str,
        target: Model,
        access: GlueAccess = GlueAccess.VIEW,
        fields: Sequence[str] | Literal['__all__'] = (),
        exclude: Sequence[str] | Literal['__all__'] = (),
        form: FormOrClass | None = None,
        forms: Mapping[str, FormOrClass] | None = None,
        select_related: Sequence[str] | None = None,
        computed_attributes: Mapping[str, ComputedAttribute] | None = None,
        related_field_config: Mapping[str, Mapping[str, Sequence[str] | Literal['__all__']]] | None = None,
        loading_strategy: LoadingStrategy = LoadingStrategy.LAZY,
    ) -> ModelGlue:
        return Glue.object(
            request=request,
            glue=ModelGlue(
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
        request: HttpRequest,
        unique_name: str,
        target: QuerySet,
        access: GlueAccess = GlueAccess.VIEW,
        fields: Sequence[str] | Literal['__all__'] = (),
        exclude: Sequence[str] | Literal['__all__'] = (),
        form: FormOrClass | None = None,
        forms: Mapping[str, FormOrClass] | None = None,
        computed_attributes: Mapping[str, ComputedAttribute] | None = None,
        related_field_config: Mapping[str, Mapping[str, Sequence[str] | Literal['__all__']]] | None = None,
        loading_strategy: LoadingStrategy = LoadingStrategy.LAZY,
    ) -> QuerySetGlue:
        return Glue.object(
            request=request,
            glue=QuerySetGlue(
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
            ),
        )

    @staticmethod
    def form(
        request: HttpRequest,
        unique_name: str,
        target: BaseForm,
        access: GlueAccess = GlueAccess.CHANGE,
        loading_strategy: LoadingStrategy = LoadingStrategy.LAZY,
    ) -> FormGlue:
        return Glue.object(
            request=request,
            glue=FormGlue(
                form=target,
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

    @staticmethod
    def json(
        request: HttpRequest,
        unique_name: str,
        target: JsonValue,
        access: GlueAccess = GlueAccess.VIEW,
        loading_strategy: LoadingStrategy = LoadingStrategy.LAZY,
    ) -> JsonGlue:
        return Glue.object(
            request=request,
            glue=JsonGlue(
                target,
                name=unique_name,
                access=access,
                loading_strategy=loading_strategy,
            ),
        )
