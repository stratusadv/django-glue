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
from django_glue.utils import get_attr_from_path_string

if TYPE_CHECKING:
    from django.http import HttpRequest
    from django.db import models


class QuerySetGlue(BaseGlue):
    namespace = 'querySet'

    def __init__(
        self,
        queryset: models.QuerySet,
        *,
        request: HttpRequest,
        name: str,
        access: GlueAccess,
        fields: Sequence[str] = (),
        exclude: Sequence[str] = (),
    ) -> None:
        super().__init__(request=request, name=name, access=access)
        self.queryset = queryset
        self.fields = tuple(fields)
        self.exclude = tuple(exclude)

    @cached_property
    def identity(self) -> dict[str, Any]:
        return {
            'model_class_path': f'{self.queryset.model.__module__}.{self.queryset.model.__name__}',
            'encoded_queryset': self._encode_queryset_query(self.queryset),
            'pk_field_name': self.queryset.model._meta.pk.name,
        }

    def get_field_names(self) -> list[str]:
        names = self.fields or tuple(
            field.name
            for field in [*self.queryset.model._meta.fields, *self.queryset.model._meta.many_to_many]
        )
        excluded = set(self.exclude)
        return [name for name in names if name not in excluded]

    @cached_property
    def attributes(self) -> dict[str, BaseGlueAttribute]:
        model_instance = self.queryset.model()
        model_object = ModelGlue(
            model_instance,
            request=self.request,
            name=f'{self.name}.__model__',
            access=self.access,
            fields=self.get_field_names(),
        )
        model_declared_names = set(discover_glue_attributes(model_object))
        attributes = {
            name: attribute
            for name, attribute in model_object.attributes.items()
            if name in self.get_field_names() or name not in model_declared_names
        }
        attributes.update(discover_glue_attributes(self))
        return attributes

    @property
    def state(self) -> dict[str, Any]:
        return {}

    @cached_property
    def metadata(self) -> GlueMetadata:
        model_instance = self.queryset.model()
        return ModelGlue(
            model_instance,
            request=self.request,
            name=f'{self.name}.__model__',
            access=self.access,
            fields=self.get_field_names(),
        ).metadata

    @classmethod
    def from_policy(cls, policy: GluePolicy, request: HttpRequest) -> QuerySetGlue:
        queryset = cls._decode_queryset_query(policy.identity['encoded_queryset'])
        glue_object = cls(
            queryset,
            request=request,
            name=policy.name,
            access=policy.access,
            fields=cls._field_names_from_policy(policy, queryset.model),
        )
        glue_object.policy = policy
        return glue_object

    @classmethod
    def _field_names_from_policy(
        cls,
        policy: GluePolicy,
        model_class: type[models.Model],
    ) -> list[str]:
        return ModelGlue.field_names_from_policy(policy, model_class)

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
        policy: GluePolicy,
        request: HttpRequest,
    ) -> dict[str, Any]:
        queryset = self.queryset
        allowed_fields = set(self._field_names_from_policy(policy, queryset.model))

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
            request=self.request,
            name=child_name,
            access=self.policy.access,
            fields=self._field_names_from_policy(self.policy, instance.__class__),
        )

        return {
            **child_object.manifest.model_dump(),
            'state': child_object.state,
        }
