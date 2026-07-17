from __future__ import annotations

from typing import Any, TYPE_CHECKING

from django.db.models.fields.files import FieldFile

from django_glue.glue.attributes.django.field import BaseDjangoFieldGlueAttribute

if TYPE_CHECKING:
    from django.db import models

    from django_glue.access import GlueAccess
    from django_glue.glue.base import BaseGlue


class ModelFieldAttribute(BaseDjangoFieldGlueAttribute):
    """GlueAttribute for a Django model field."""

    def __init__(
        self,
        *,
        owner: BaseGlue,
        name: str,
        field: models.Field,
        instance: models.Model,
        access: GlueAccess,
    ) -> None:
        super().__init__(owner=owner, name=name, field=field, access=access)
        self.instance = instance

    def add_extra_metadata(self, metadata: dict[str, Any]) -> None:
        metadata['editable'] = self.field.editable
        metadata['disabled'] = not self.field.editable
        if getattr(self.field, 'is_relation', False) and getattr(self.field, 'related_model', None):
            metadata['choices'] = []
            metadata['pk_field'] = self.field.related_model._meta.pk.name
            metadata['choice_model_path'] = (
                f'{self.field.related_model.__module__}.{self.field.related_model.__name__}'
            )
            metadata['related_model'] = metadata['choice_model_path']
            metadata['choices_cache_key'] = (
                f'{self.instance.__class__._meta.label_lower}.{self.name}.'
                f'{self.field.related_model._meta.label_lower}'
            )

    def get(self) -> Any:
        if getattr(self.field, 'many_to_many', False):
            if self.instance.pk is None:
                return []
            return [
                {'pk': obj.pk, '__str__': f'{obj}'}
                for obj in self.field.value_from_object(self.instance)
            ]

        value = self.field.value_from_object(self.instance)
        if isinstance(value, FieldFile):
            return self._serialize_field_file(value)
        return value

    @staticmethod
    def _serialize_field_file(value: FieldFile) -> dict[str, Any] | None:
        try:
            return {
                'name': value.name,
                'size': value.size,
                'url': value.url,
                'path': value.path,
            }
        except ValueError:
            return None

    def set(self, value: Any) -> None:
        if self.field.editable:
            self.field.save_form_data(self.instance, value)
