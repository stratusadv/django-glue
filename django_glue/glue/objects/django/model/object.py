from __future__ import annotations

from functools import cached_property
from typing import Any, Sequence, TYPE_CHECKING

from django.forms import modelform_factory
from django.utils.datastructures import MultiValueDict

from django_glue.access import GlueAccess
from django_glue.glue.attributes import BaseGlueAttribute, discover_glue_attributes
from django_glue.glue.base import BaseGlue
from django_glue.glue.attributes.django.model import DjangoModelFieldGlueAttribute
from django_glue.glue.metadata import GlueMetadata
# Runtime import required: Glue.Attribute method annotations are resolved with
# typing.get_type_hints() when building callable kwargs.
from django_glue.glue.policy import GluePolicy
from django_glue.glue.attributes import Attribute
from django_glue.utils import get_attr_from_path_string

if TYPE_CHECKING:
    from django import forms
    from django.db import models
    from django.http import HttpRequest


class ModelGlue(BaseGlue):
    namespace = 'model'

    def __init__(
        self,
        instance: models.Model,
        *,
        request: HttpRequest,
        name: str,
        access: GlueAccess,
        fields: Sequence[str] = (),
        exclude: Sequence[str] = (),
        form_class: type[forms.ModelForm] | None = None,
    ) -> None:
        super().__init__(request=request, name=name, access=access)
        self.instance = instance
        self.fields = tuple(fields)
        self.exclude = tuple(exclude)
        self.form_class = form_class

    @cached_property
    def identity(self) -> dict[str, Any]:
        instance = self.instance
        return {
            'model_class_path': f'{instance.__class__.__module__}.{instance.__class__.__name__}',
            'target_pk': instance.pk,
            'pk_field_name': instance._meta.pk.name,
        }

    @cached_property
    def attributes(self) -> dict[str, BaseGlueAttribute]:
        attributes = {
            field_name: DjangoModelFieldGlueAttribute(
                name=field_name,
                field=self.instance._meta.get_field(field_name),
                instance=self.instance,
                access=self._field_access(field_name),
            )
            for field_name in self.get_field_names()
        }
        attributes.update(discover_glue_attributes(self))
        attributes.update(discover_glue_attributes(self.instance))
        return attributes

    def get_field_names(self) -> list[str]:
        names = self.fields or tuple(
            field.name
            for field in [*self.instance._meta.fields, *self.instance._meta.many_to_many]
        )
        excluded = set(self.exclude)
        return [name for name in names if name not in excluded]

    @property
    def state(self) -> dict[str, Any]:
        data: dict[str, Any] = {}
        for field_name in self.get_field_names():
            data[field_name] = self.attributes[field_name].get_value()
        return {'instance_data': data, 'errors': {}}

    @cached_property
    def metadata(self) -> GlueMetadata:
        fields: dict[str, Any] = {}
        for field_name in self.get_field_names():
            fields[field_name] = self.attributes[field_name].metadata
        return GlueMetadata.from_payload({
            'namespace': self.namespace,
            'fields': fields,
            'attributes': {
                name: attribute.metadata
                for name, attribute in self.attributes.items()
                if name not in fields
            },
        })

    def _field_access(self, field_name: str) -> GlueAccess:
        field = self.instance._meta.get_field(field_name)
        return GlueAccess.CHANGE if field.editable else GlueAccess.VIEW

    @staticmethod
    def field_names_from_policy(policy: GluePolicy, model_class: type[models.Model]) -> list[str]:
        model_field_names = {
            field.name
            for field in [*model_class._meta.fields, *model_class._meta.many_to_many]
        }
        return [
            attribute_name
            for attribute_name in policy.attributes
            if attribute_name in model_field_names
        ]

    @classmethod
    def from_policy(cls, policy: GluePolicy, request: HttpRequest) -> ModelGlue:
        model_class = get_attr_from_path_string(policy.identity['model_class_path'])
        target_pk = policy.identity.get('target_pk')
        instance = model_class() if target_pk is None else model_class.objects.get(pk=target_pk)
        glue_object = cls(
            instance,
            request=request,
            name=policy.name,
            access=policy.access,
            fields=cls.field_names_from_policy(policy, model_class),
        )
        glue_object.policy = policy
        return glue_object

    def apply_state(
        self,
        state: dict[str, Any],
        policy: GluePolicy,
        request: HttpRequest | None = None,
    ) -> forms.ModelForm:
        target = self.instance
        editable_fields = [
            name for name in self.field_names_from_policy(policy, target.__class__)
            if target._meta.get_field(name).editable
        ]
        form_class = self.form_class or modelform_factory(target.__class__, fields=editable_fields)
        form = form_class(
            data=self._form_data_from_state(state.get('instance_data', {}), editable_fields),
            files=self._form_files_from_request(request, editable_fields),
            instance=target,
        )
        if form.is_valid():
            form.save()
        return form

    @Attribute(access=GlueAccess.VIEW)
    def load(self) -> dict[str, Any]:
        return {'state': self.state}

    @Attribute(access=GlueAccess.CHANGE)
    def save(
        self,
        state: dict[str, Any],
        policy: GluePolicy,
        request: HttpRequest,
    ) -> dict[str, Any]:
        form = self.apply_state(state or {}, policy, request)
        return {'valid': not bool(form.errors), 'errors': dict(form.errors)}

    @Attribute(access=GlueAccess.CHANGE)
    def validate(
        self,
        state: dict[str, Any],
        policy: GluePolicy,
        request: HttpRequest,
    ) -> dict[str, Any]:
        form = self.apply_state(state or {}, policy, request)
        return {'success': not bool(form.errors), 'valid': not bool(form.errors), 'errors': dict(form.errors)}

    def _form_data_from_state(
        self,
        instance_data: dict[str, Any],
        field_names: Sequence[str],
    ) -> dict[str, Any]:
        data: dict[str, Any] = {}
        for field_name in field_names:
            field = self.instance._meta.get_field(field_name)
            value = instance_data.get(field_name)

            if getattr(field, 'many_to_many', False):
                data[field_name] = [self._pk_from_related_value(item) for item in value or []]
                continue

            if getattr(field, 'many_to_one', False) or getattr(field, 'one_to_one', False):
                data[field_name] = self._pk_from_related_value(value)
                continue

            if getattr(field, 'get_internal_type', lambda: '')() in {'FileField', 'ImageField'}:
                if value in (None, ''):
                    data[field_name] = value
                continue

            data[field_name] = value
        return data

    @staticmethod
    def _form_files_from_request(
        request: HttpRequest | None,
        field_names: Sequence[str],
    ) -> MultiValueDict | None:
        if request is None or not request.FILES:
            return None

        files = MultiValueDict()
        for field_name in field_names:
            for request_key in (field_name, f'instance_data.{field_name}'):
                if request_key not in request.FILES:
                    continue
                if hasattr(request.FILES, 'getlist'):
                    files.setlist(field_name, request.FILES.getlist(request_key))
                else:
                    files.setlist(field_name, [request.FILES[request_key]])

        return files or None

    @staticmethod
    def _pk_from_related_value(value: Any) -> Any:
        if isinstance(value, dict):
            return value.get('pk', value.get('id'))
        return getattr(value, 'pk', value)

    @Attribute(access=GlueAccess.VIEW)
    def foreign_key_choices(
        self,
        field_name: str | None = None,
        choice_fields: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        if not field_name or field_name not in self.get_field_names():
            return []

        field = self.instance._meta.get_field(field_name)
        related_model = getattr(field, 'related_model', None)
        if related_model is None:
            return []

        def serialize_choice(obj) -> dict[str, Any]:
            choice = {'pk': obj.pk, '__str__': f'{obj}'}
            for choice_field in choice_fields or []:
                choice[choice_field] = getattr(obj, choice_field)
            return choice

        return [serialize_choice(obj) for obj in related_model.objects.all()]

    @Attribute(access=GlueAccess.DELETE)
    def delete(self) -> dict[str, Any]:
        self.instance.delete()
        return {}
