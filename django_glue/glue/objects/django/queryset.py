from __future__ import annotations

import base64
import builtins
import pickle
from functools import cached_property
from typing import Any, Literal, Mapping, Sequence, TYPE_CHECKING

from django import forms

from django_glue.access import GlueAccess
from django_glue.glue.attributes import BaseGlueAttribute
from django_glue.glue.base import BaseGlue
from django_glue.glue.metadata import GlueMetadata
from django_glue.glue.objects.django.form.mixin import ModelGlueFormConfigMixin
from django_glue.glue.objects.django.model.object import ALL_FIELDS, ModelGlue
# Runtime import required: Glue.Attribute method annotations are resolved with
# typing.get_type_hints() when building callable kwargs.
from django_glue.glue.policy import GluePolicy
from django_glue.glue.attributes import DeclaredAttribute
from django_glue.exceptions import GlueQuerySetFilterValidationError

if TYPE_CHECKING:
    from django.db import models


class QuerySetGlue(ModelGlueFormConfigMixin, BaseGlue):
    namespace = 'querySet'

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
    ) -> None:
        super().__init__(name=name, access=access)
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

    @property
    def identity(self) -> dict[str, Any]:
        identity = {
            'model_class_path': f'{self.queryset.model.__module__}.{self.queryset.model.__name__}',
            'encoded_queryset': self._encode_queryset_query(self.queryset),
            'pk_field_name': self.queryset.model._meta.pk.name,
        }
        if self.forms:
            identity['form_identities'] = self.serialize_forms(self.forms)

        return identity

    @property
    def attribute_providers(self) -> dict[str, Any]:
        return {}

    @cached_property
    def _included_fields(self) -> list[str]:
        all_field_names = tuple(
            field.name
            for field in [
                *self.queryset.model._meta.fields,
                *self.queryset.model._meta.many_to_many
            ]
        )
        names = all_field_names if self.fields == ALL_FIELDS or not self.fields else self.fields
        excluded = set(all_field_names) if self.exclude == ALL_FIELDS else set(self.exclude)
        return [
            name
            for name in names
            if name not in excluded
            and self.queryset.model._meta.get_field(name).get_internal_type()
            not in ModelGlue.globally_excluded_field_types
        ]

    @cached_property
    def _select_related_fields(self) -> set[str]:
        select_related = self.queryset.query.select_related
        if isinstance(select_related, dict):
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
            annotations=tuple(self.queryset.query.annotations),
            forms=self.forms,
            select_related=self._select_related_fields,
        )
        # Get field attributes from the model, excluding model's declared attributes
        field_names = {*self._included_fields, *self._annotation_names}
        attributes: dict[str, BaseGlueAttribute] = {
            name: attribute
            for name, attribute in model_object.attributes.items()
            if name in field_names
        }
        # Add our own declared attributes
        attributes.update(super().attributes)
        return attributes

    @property
    def state(self) -> dict[str, Any]:
        # QuerySet has no instance-level state - individual items have their own state
        return {}

    @cached_property
    def metadata(self) -> GlueMetadata:
        return GlueMetadata.from_payload({
            'attributes': {
                name: attribute.metadata
                for name, attribute in self.attributes.items()
            },
        })

    @cached_property
    def _annotation_names(self) -> tuple[str, ...]:
        return tuple(self.queryset.query.annotations)

    @classmethod
    def _reconstruct_from_policy(cls, policy: GluePolicy) -> QuerySetGlue:
        queryset = cls._decode_queryset_query(policy.identity['encoded_queryset'])
        model_field_names = {
            field.name
            for field in [*queryset.model._meta.fields, *queryset.model._meta.many_to_many]
        }
        fields = [
            attr
            for attr in policy.attributes
            if isinstance(attr, str) and attr in model_field_names
        ]
        forms = cls.deserialize_form_classes(
            policy.identity.get('form_identities', {})
        )
        return cls(
            queryset,
            name=policy.name,
            access=policy.access,
            fields=fields,
            forms=forms,
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

    @DeclaredAttribute(access=GlueAccess.VIEW)
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

    @DeclaredAttribute(access=GlueAccess.VIEW)
    def get(self, pk: Any) -> dict[str, Any]:
        return self._build_child_model_payload(self.queryset.get(pk=pk))

    @DeclaredAttribute(access=GlueAccess.VIEW)
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
        if self.queryset.query.select_related:
            select_related = set(self.queryset.query.select_related)
        else:
            select_related = set()

        child_object = ModelGlue(
            instance,
            name=child_name,
            access=self.policy.access,
            fields=self._included_fields,
            annotations=tuple(self.queryset.query.annotations),
            forms=child_forms,
            select_related=select_related
        )
        child_object.request = self.request

        return {
            **child_object.manifest.model_dump(),
            'state': child_object.state,
        }
