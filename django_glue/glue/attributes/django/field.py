from __future__ import annotations

from typing import Any, TYPE_CHECKING

from django_glue.access import GlueAccess
from django_glue.glue.attributes.state import StateAttribute

if TYPE_CHECKING:
    from django_glue.glue.base import BaseGlue


class BaseDjangoFieldGlueAttribute(StateAttribute):
    """
    Base class for Django field-backed attributes.

    These attributes get their value directly from a Django field rather
    than using path-based lookup. They provide rich metadata about the
    field type, validation rules, and choices.
    """

    def __init__(
        self,
        *,
        owner: BaseGlue,
        name: str,
        field: Any,
        access: GlueAccess,
    ) -> None:
        super().__init__(owner=owner, name=name, access=access)
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

        namespace = getattr(self, 'namespace', 'field')
        return super().metadata | metadata | {'namespace': namespace}

    @property
    def label(self) -> str:
        label = str(getattr(self.field, 'label', None) or getattr(self.field, 'verbose_name', '') or '')
        return label.capitalize() if label else ''

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
