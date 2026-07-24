from __future__ import annotations

import base64
import pickle
from functools import cached_property
from typing import Any, Sequence, TYPE_CHECKING


from django_glue.access import GlueAccess
from django_glue.glue.attributes import BaseGlueAttribute
from django_glue.glue.base import BaseGlue
from django_glue.glue.objects.django.model.object import ModelGlue
from django_glue.glue.metadata import GlueMetadata
# Runtime import required: Glue.Attribute method annotations are resolved with
# typing.get_type_hints() when building callable kwargs.
from django_glue.glue.policy import GluePolicy
from django_glue.glue.attributes import Attribute
from django_glue.exceptions import GlueQuerySetFilterValidationError

if TYPE_CHECKING:
    from django.db import models


class QuerySetGlue(BaseGlue):
    namespace = 'querySet'

    def __init__(
        self,
        queryset: models.QuerySet,
        *,
        name: str,
        access: GlueAccess,
        fields: Sequence[str] = (),
        exclude: Sequence[str] = (),
    ) -> None:
        super().__init__(name=name, access=access)
        self.queryset = queryset
        self.fields = tuple(fields)
        self.exclude = tuple(exclude)

    @property
    def identity(self) -> dict[str, Any]:
        return {
            'model_class_path': f'{self.queryset.model.__module__}.{self.queryset.model.__name__}',
            'encoded_queryset': self._encode_queryset_query(self.queryset),
            'pk_field_name': self.queryset.model._meta.pk.name,
        }

    @property
    def attribute_providers(self) -> dict[str, Any]:
        return {}

    @cached_property
    def _included_fields(self) -> list[str]:
        names = self.fields or tuple(
            field.name
            for field in [
                *self.queryset.model._meta.fields,
                *self.queryset.model._meta.many_to_many
            ]
        )
        excluded = set(self.exclude)
        return [name for name in names if name not in excluded]

    @cached_property
    def attributes(self) -> dict[str, BaseGlueAttribute]:
        model_instance = self.queryset.model()
        model_object = ModelGlue(
            model_instance,
            name=f'{self.name}.__model__',
            access=self.access,
            fields=self._included_fields,
            source_queryset=self.queryset,
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
    def _from_policy(cls, policy: GluePolicy) -> QuerySetGlue:
        queryset = cls._decode_queryset_query(policy.identity['encoded_queryset'])
        model_field_names = {
            field.name
            for field in [*queryset.model._meta.fields, *queryset.model._meta.many_to_many]
        }
        fields = [
            attr_name
            for attr_name in policy.attributes
            if attr_name in model_field_names
        ]
        glue_object = cls(
            queryset,
            name=policy.name,
            access=policy.access,
            fields=fields,
        )
        glue_object.policy = policy
        return glue_object

    @staticmethod
    def _encode_queryset_query(queryset: models.QuerySet) -> str:
        return base64.b64encode(pickle.dumps(queryset.query)).decode('utf-8')

    @staticmethod
    def _decode_queryset_query(encoded_query: str) -> models.QuerySet:
        query = pickle.loads(base64.b64decode(encoded_query))
        queryset = query.model.objects.all()
        queryset.query = query
        return queryset

    @Attribute(access=GlueAccess.VIEW)
    def query_with_params(
        self,
        kwargs: dict[str, Any],
    ) -> dict[str, Any]:
        queryset = self.queryset
        allowed_fields = set(self._included_fields)

        for key in (kwargs.get('filter') or {}):
            base_field = key.split('__')[0]
            if base_field not in allowed_fields:
                raise GlueQuerySetFilterValidationError(base_field, list(allowed_fields))

        if kwargs.get('filter'):
            queryset = queryset.filter(**kwargs['filter'])
        if kwargs.get('order_by'):
            order_by = kwargs['order_by']
            if isinstance(order_by, str):
                order_by = [order_by]
            queryset = queryset.order_by(*order_by)
        if kwargs.get('slice'):
            slice_data = kwargs['slice']
            queryset = queryset[slice(slice_data.get('start'), slice_data.get('stop'))]

        self.queryset = queryset

        items = [self._build_child_model_payload(instance) for instance in queryset]
        return {'items': items, 'query': {}}

    def _build_child_model_payload(self, instance: models.Model) -> dict[str, Any]:
        child_name = f'{self.policy.name}.{instance.pk}'
        child_object = ModelGlue(
            instance,
            name=child_name,
            access=self.policy.access,
            fields=self._included_fields,
            source_queryset=self.queryset,
        )
        child_object.request = self.request

        return {
            **child_object.manifest.model_dump(),
            'state': child_object.state,
        }
