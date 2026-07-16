from __future__ import annotations

from typing import Any

from django_glue.access import GlueAccess
from django_glue.glue.attributes import BaseGlueAttribute


class BaseDjangoFieldGlueAttribute(BaseGlueAttribute):
    """Shared metadata behavior for Django field-backed attributes."""

    def __init__(
        self,
        *,
        name: str,
        field: Any,
        access: GlueAccess,
    ) -> None:
        super().__init__(name=name, required_access=access, is_callable=False)
        self.field = field

    @property
    def metadata(self) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            'type': self.field.__class__.__name__,
            'label': self.label,
            'required': self.required,
            'help_text': self.help_text,
        }
        self.add_length_metadata(metadata)
        self.add_choice_metadata(metadata)
        self.add_extra_metadata(metadata)
        return metadata

    @property
    def label(self) -> str:
        return str(getattr(self.field, 'label', None) or getattr(self.field, 'verbose_name', '') or '')

    @property
    def required(self) -> bool:
        if hasattr(self.field, 'required'):
            return bool(self.field.required)
        return not getattr(self.field, 'blank', False) and not getattr(self.field, 'null', False)

    @property
    def help_text(self) -> str:
        return str(getattr(self.field, 'help_text', '') or '')

    def add_length_metadata(self, metadata: dict[str, Any]) -> None:
        if getattr(self.field, 'max_length', None):
            metadata['max_length'] = self.field.max_length
        if getattr(self.field, 'min_length', None):
            metadata['min_length'] = self.field.min_length

    def add_choice_metadata(self, metadata: dict[str, Any]) -> None:
        if getattr(self.field, 'choices', None):
            metadata['choices'] = [
                (str(value), str(label))
                for value, label in self.field.choices
            ]

    def add_extra_metadata(self, metadata: dict[str, Any]) -> None:
        return None
