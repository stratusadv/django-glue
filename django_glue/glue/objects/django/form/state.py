"""A Django form held as an attribute's state (ADR 042)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from django import forms
from django.core.exceptions import NON_FIELD_ERRORS

from django_glue.serialization import GlueSerializer, GlueSerializerError, glue_serializer_registry
from django_glue.glue.attributes.description import GlueFieldDescription
from django_glue.glue.attributes.value_adapters import DEFAULT_VALUE_ADAPTERS
from django_glue.glue.objects.django.fields.description import field_schema

if TYPE_CHECKING:
    from collections.abc import Callable

    from django_glue.glue.attributes.declared import DeclaredAttribute


def _field_values(form: forms.BaseForm) -> dict[str, Any]:
    """Each field's value as the form renders it: its data when bound, its initial otherwise."""
    return {bound_field.name: bound_field.value() for bound_field in form}


class FormSerializer(GlueSerializer):
    """A form class: its fields' values on the wire, and in Python the form bound to them."""

    @classmethod
    def supports(cls, target: Any) -> bool:
        return isinstance(target, type) and issubclass(target, forms.BaseForm)

    def __init__(self, target: type[forms.BaseForm]) -> None:
        super().__init__(target)
        for name, field in target.base_fields.items():
            if isinstance(field, forms.FileField):
                reason = 'a file is uploaded, not held as state'
            elif isinstance(field.widget, forms.PasswordInput) and not field.widget.render_value:
                reason = 'a write-only value is never signed or sent back'
            elif hasattr(field, 'queryset'):
                reason = 'the form is built from its values alone, so nothing narrows its queryset'
            else:
                continue
            message = f'{target.__name__}.{name} cannot be held as state: {reason}.'
            raise GlueSerializerError(message)

    def load(self, raw: Any) -> forms.BaseForm:
        if isinstance(raw, self.target):
            return raw
        if not isinstance(raw, Mapping):
            message = f'{self.target.__name__} state must be an object of field values.'
            raise GlueSerializerError(message)
        unknown = sorted(set(raw) - set(self.target.base_fields))
        if unknown:
            message = f'{self.target.__name__} has no fields {unknown!r}.'
            raise GlueSerializerError(message)
        return self.target(data=dict(raw))

    def dump(self, value: forms.BaseForm) -> dict[str, Any]:
        return _field_values(value)

    def default(self) -> forms.BaseForm:
        return self.target()

    def description(
        self,
        *,
        read: Callable[[], forms.BaseForm],
        editable: bool,
    ) -> FormStateDescription:
        return FormStateDescription(form_class=self.target, read=read, editable=editable)


@dataclass(frozen=True, slots=True)
class FormStateDescription(GlueFieldDescription):
    form_class: type[forms.BaseForm]
    read: Callable[[], forms.BaseForm]
    editable: bool

    def schema(self) -> dict[str, Any]:
        return {
            'editable': self.editable,
            'fields': {
                name: {
                    **field_schema(field, editable=self.editable),
                    'widget': field.widget.__class__.__name__,
                }
                for name, field in self.form_class.base_fields.items()
            },
        }

    def computed_data(self) -> dict[str, Any]:
        """
        The errors of a validation that already ran. Reading ``form.errors``
        would run one, and report every required field of a form nobody has
        submitted.
        """
        errors = self.read()._errors
        if errors is None:
            return {'errors': [], 'field_errors': {}}
        return {
            'errors': list(errors.get(NON_FIELD_ERRORS, ())),
            'field_errors': {
                name: list(field_errors)
                for name, field_errors in errors.items()
                if name != NON_FIELD_ERRORS
            },
        }


class UnboundFormBinder:
    """
    Binds an unbound form assigned to an attribute to its own initial values,
    so it validates before the browser has sent any.
    """

    def applies_to(self, value: Any, *, attribute: DeclaredAttribute) -> bool:
        _ = attribute
        return isinstance(value, forms.BaseForm) and not value.is_bound

    def adapt(self, value: forms.BaseForm, *, attribute: DeclaredAttribute, instance: Any) -> Any:
        _ = instance
        if isinstance(value, forms.BaseModelForm) and value.instance.pk is not None:
            message = (
                f'Attribute {attribute.name!r} cannot hold a form over a saved record: '
                'a form that edits a record is a Glue.child.'
            )
            raise TypeError(message)
        return type(value)(data=_field_values(value))


glue_serializer_registry.register(FormSerializer)
DEFAULT_VALUE_ADAPTERS.append(UnboundFormBinder())
