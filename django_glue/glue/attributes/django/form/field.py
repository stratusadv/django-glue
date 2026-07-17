from __future__ import annotations

from typing import Any, TYPE_CHECKING

from django_glue.glue.attributes.django.field import BaseDjangoFieldGlueAttribute

if TYPE_CHECKING:
    from django import forms

    from django_glue.access import GlueAccess
    from django_glue.glue.base import BaseGlue


class FormFieldAttribute(BaseDjangoFieldGlueAttribute):
    """GlueAttribute for a Django form field."""

    def __init__(
        self,
        *,
        owner: BaseGlue,
        name: str,
        field: forms.Field,
        form: forms.BaseForm,
        access: GlueAccess,
    ) -> None:
        super().__init__(owner=owner, name=name, field=field, access=access)
        self.form = form

    def add_choice_metadata(self, metadata: dict[str, Any]) -> None:
        if hasattr(self.field, 'queryset'):
            metadata['choices'] = []
            metadata['pk_field'] = self.field.queryset.model._meta.pk.name
            metadata['choice_model_path'] = (
                f'{self.field.queryset.model.__module__}.{self.field.queryset.model.__name__}'
            )
            metadata['choices_cache_key'] = (
                f'{self.form.__class__.__module__}.{self.form.__class__.__name__}.'
                f'{self.name}.{self.field.queryset.model._meta.label_lower}'
            )
            return
        super().add_choice_metadata(metadata)

    def add_extra_metadata(self, metadata: dict[str, Any]) -> None:
        metadata['disabled'] = self.field.disabled
        metadata['widget'] = self.field.widget.__class__.__name__

    def get(self) -> Any:
        if self.form.is_bound:
            return self.form.data.get(self.name)
        return self.form.initial.get(self.name)
