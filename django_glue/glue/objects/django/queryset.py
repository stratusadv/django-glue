from __future__ import annotations

import base64
import builtins
import pickle
from functools import cached_property
from typing import Any, Literal, Mapping, Sequence, TYPE_CHECKING

from django_glue.access import GlueAccess
from django_glue.exceptions import GlueQuerySetFilterValidationError
from django_glue.glue.attributes import BaseGlueAttribute
from django_glue.glue.attributes import DeclaredAttribute
from django_glue.glue.base import BaseGlue
from django_glue.glue.loading import LoadingStrategy
from django_glue.glue.objects.django.computed_attributes import (
    ComputedAttribute,
    GlueComputedAttributesMixin,
)
from django_glue.glue.objects.django.form.mixin import ModelGlueFormConfigMixin
from django_glue.glue.objects.django.model.object import ALL_FIELDS, ModelGlue
from django_glue.glue.objects.django.model_fields import ModelFieldResolutionMixin

if TYPE_CHECKING:
    from django import forms
    from django.db import models
    from django_glue.glue.policy import GluePolicy


class QuerySetGlue(GlueComputedAttributesMixin, ModelGlueFormConfigMixin, ModelFieldResolutionMixin, BaseGlue):
    namespace = 'querySet'
    globally_excluded_field_types = ModelGlue.globally_excluded_field_types

    def __init__(
        self,
        queryset: models.QuerySet,
        *,
        name: str,
        access: GlueAccess,
        fields: Sequence[str] | Literal['__all__'] = (),
        exclude: Sequence[str] | Literal['__all__'] = (),
        form: forms.ModelForm | None = None,
        forms: Mapping[str, forms.ModelForm] | None = None,
        computed_attributes: Mapping[str, ComputedAttribute] | None = None,
        related_field_config: Mapping[str, Mapping[str, Sequence[str] | Literal['__all__']]] | None = None,
        loading_strategy: LoadingStrategy = LoadingStrategy.LAZY,
    ) -> None:
        super().__init__(name=name, access=access, loading_strategy=loading_strategy)
        self.queryset = queryset
        self.fields = (
            fields if fields == ALL_FIELDS else tuple(fields)
        )
        self.exclude = (
            exclude if exclude == ALL_FIELDS else tuple(exclude)
        )

        if not self.fields and not self.exclude:
            msg = 'QuerySetGlue requires at least one of fields or exclude.'
            raise ValueError(msg)

        self.forms = self.normalize_forms(form, forms)
        self.related_field_config = ModelGlue._normalize_related_field_config(related_field_config)
        self._select_related = self._get_select_related_fields()
        self.initialize_computed_attributes(computed_attributes)

    def get_identity(self) -> dict[str, Any]:
        identity = {
            'model_class_path': f'{self.queryset.model.__module__}.{self.queryset.model.__name__}',
            'encoded_queryset': self._encode_queryset_query(self.queryset),
            'pk_field_name': self.queryset.model._meta.pk.name,
        }
        if self.forms:
            identity['form_identities'] = self.serialize_forms(self.forms)
        if self.related_field_config:
            identity['related_field_config'] = self.related_field_config
        identity |= self.computed_attributes_identity()

        return identity

    def get_attribute_providers(self) -> dict[str, Any]:
        return {}

    @property
    def _model_meta(self) -> Any:
        """Return the Django model's _meta options."""
        return self.queryset.model._meta

    def _get_select_related_fields(self) -> set[str]:
        select_related = self.queryset.query.select_related
        if isinstance(select_related, dict):
            # TODO: Preserve nested select_related paths instead of only top-level fields.
            return set(select_related.keys())
        return set()

    @cached_property
    def attributes(self) -> dict[str, BaseGlueAttribute]:
        model_instance = self.queryset.model()
        model_object = ModelGlue(
            model_instance,
            name=f'{self.name}.__model__',
            access=self.access,
            fields=self._included_fields,
            annotations=self._orm_annotation_names,
            forms=self.forms,
            select_related=self._select_related,
            computed_attributes=self.computed_attributes,
            related_field_config=self.related_field_config,
        )
        # Get field attributes from the model, excluding model's declared attributes
        field_names = {
            *self._included_fields,
            *self._orm_annotation_names,
            *self._computed_attribute_names,
        }
        attributes: dict[str, BaseGlueAttribute] = {
            name: attribute
            for name, attribute in model_object.attributes.items()
            if name in field_names
        }
        # Add our own declared attributes
        attributes.update(super().attributes)
        return attributes

    def get_state(self) -> dict[str, Any]:
        return {
            'items': [
                self._build_child_model_payload(instance)
                for instance in self.queryset
            ],
        }

    def get_metadata(self) -> dict[str, Any]:
        return {
            'attributes': {
                name: attribute.metadata
                for name, attribute in self.attributes.items()
            },
        }

    @cached_property
    def _orm_annotation_names(self) -> tuple[str, ...]:
        return tuple(self.queryset.query.annotations)

    @classmethod
    def _reconstruct_from_policy(cls, policy: GluePolicy) -> QuerySetGlue:
        queryset = cls._decode_queryset_query(policy.identity['encoded_queryset'])
        all_field_names = set(cls._all_available_field_names_for_meta(queryset.model._meta))
        fields = [
            attr
            for attr in policy.attributes
            if isinstance(attr, str) and attr in all_field_names
        ]
        forms = cls.deserialize_form_classes(
            policy.identity.get('form_identities', {})
        )
        related_field_config = policy.identity.get('related_field_config', {})
        return cls(
            queryset,
            name=policy.name,
            access=policy.access,
            fields=fields,
            forms=forms,
            computed_attributes=policy.identity.get('computed_attributes', {}),
            related_field_config=related_field_config,
        )

    @staticmethod
    def _encode_queryset_query(queryset: models.QuerySet) -> str:
        return base64.b64encode(pickle.dumps(queryset.query)).decode('utf-8')

    @staticmethod
    def _decode_queryset_query(encoded_query: str) -> models.QuerySet:
        query = pickle.loads(base64.b64decode(encoded_query))
        queryset = query.model.objects.all()
        queryset.query = query
        return queryset

    @DeclaredAttribute(access=GlueAccess.VIEW, updates_client_state=False)
    def query_with_params(
        self,
        filter: dict[str, Any] | None = None,  # noqa: A002
        order_by: str | list[str] | None = None,
        slice: dict[str, Any] | None = None,  # noqa: A002
    ) -> dict[str, Any]:
        queryset = self.queryset
        allowed_fields = set(self._included_fields)

        for key in (filter or {}):
            base_field = key.split('__')[0]
            if base_field not in allowed_fields:
                raise GlueQuerySetFilterValidationError(base_field, list(allowed_fields))

        if filter:
            queryset = queryset.filter(**filter)
        if order_by:
            if isinstance(order_by, str):
                order_by = [order_by]
            queryset = queryset.order_by(*order_by)

        if slice:
            queryset = queryset[builtins.slice(slice.get('start'), slice.get('stop'))]

        items = [self._build_child_model_payload(instance) for instance in queryset]
        return {'items': items, 'query': {}}

    @DeclaredAttribute(access=GlueAccess.VIEW, updates_client_state=False)
    def get(self, pk: Any) -> dict[str, Any]:
        return self._build_child_model_payload(self.queryset.get(pk=pk))

    @DeclaredAttribute(access=GlueAccess.VIEW, updates_client_state=False)
    def new(self, initial: dict | None = None) -> dict[str, Any]:
        instance = self.queryset.model(**initial) if initial else self.queryset.model()
        return self._build_child_model_payload(instance=instance)

    def _build_child_model_payload(self, instance: models.Model) -> dict[str, Any]:
        child_name = f'{self.policy.name}.{instance.pk}'
        child_forms = {
            # Need to rebuild the form here in order to properly bind instance data!
            name: form.__class__(instance=instance)
            for name, form in self.forms.items()
        }
        # Child models in query results are always eager - they contain the fetched data
        child_object = ModelGlue(
            instance,
            name=child_name,
            access=self.policy.access,
            fields=self._included_fields,
            annotations=self._orm_annotation_names,
            forms=child_forms,
            select_related=self._select_related,
            computed_attributes=self.computed_attributes,
            related_field_config=self.related_field_config,
            loading_strategy=LoadingStrategy.EAGER,
        )
        child_object.request = self.request

        # Propagate visited relations for cycle detection in nested objects
        if hasattr(self, '_visited_relations'):
            child_object._visited_relations = self._visited_relations

        return child_object.manifest.model_dump()
