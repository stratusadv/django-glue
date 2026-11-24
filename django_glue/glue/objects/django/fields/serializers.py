from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django import forms
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models

from django_glue.glue.objects.django.fields.presentation import FieldAttributePresentation
from django_glue.serialization import GlueSerializer, GlueSerializerError, glue_serializer_registry

if TYPE_CHECKING:
    from collections.abc import Callable


class ModelFieldSerializer(GlueSerializer):
    """A model field's value, loaded as the field converts it."""

    @classmethod
    def supports(cls, target: Any) -> bool:
        return isinstance(target, models.Field)

    def load(self, raw: Any) -> Any:
        if isinstance(self.target, models.FileField):
            message = 'File fields are uploaded, not updated as values.'
            raise GlueSerializerError(message)
        return self._convert(raw)

    def restore(self, raw: Any) -> Any:
        if isinstance(self.target, models.FileField):
            return raw
        return self._convert(raw)

    def _convert(self, raw: Any) -> Any:
        field = self.target
        try:
            if isinstance(field, models.JSONField):
                return raw
            if getattr(field, 'many_to_many', False):
                if raw is not None and (
                    not isinstance(raw, (list, tuple))
                    or any(isinstance(item, dict) for item in raw)
                ):
                    message = 'Membership updates must be a flat list of identities.'
                    raise GlueSerializerError(message)
                return [
                    field.target_field.to_python(item)
                    for item in raw or []
                ]
            if getattr(field, 'many_to_one', False) or getattr(field, 'one_to_one', False):
                if isinstance(raw, (dict, list, tuple)):
                    message = 'Relation updates must be a raw identity value.'
                    raise GlueSerializerError(message)
                return field.target_field.to_python(raw)
            return field.to_python(raw)
        except DjangoValidationError as error:
            raise GlueSerializerError(str(error)) from error


class FormFieldSerializer(GlueSerializer):
    """
    The value of a field inside a form, declared by its bound field: held raw
    for the form to clean, so loading only refuses a wrong shape.
    """

    @classmethod
    def supports(cls, target: Any) -> bool:
        return isinstance(target, forms.BoundField)

    def load(self, raw: Any) -> Any:
        field = self.target.field
        if isinstance(field, forms.FileField):
            message = 'File fields are uploaded, not updated as values.'
            raise GlueSerializerError(message)
        if isinstance(field, forms.ModelMultipleChoiceField):
            if raw is not None and (
                not isinstance(raw, (list, tuple))
                or any(isinstance(item, dict) for item in raw)
            ):
                message = 'Choice updates must be a flat list of values.'
                raise GlueSerializerError(message)
        elif isinstance(field, forms.ModelChoiceField) and isinstance(
            raw,
            (dict, list, tuple),
        ):
            message = 'Choice updates must be a raw choice value.'
            raise GlueSerializerError(message)
        return raw

    def restore(self, raw: Any) -> Any:
        return raw


class FieldAttributeSerializer(GlueSerializer):
    """
    A form field standing alone as an attribute's type (ADR 051): the attribute
    holds what the field cleans, and the browser and the token what it prepares.
    """

    @classmethod
    def supports(cls, target: Any) -> bool:
        return isinstance(target, forms.Field)

    def __init__(self, target: forms.Field) -> None:
        super().__init__(target)
        if hasattr(target, 'queryset'):
            reason = 'nothing narrows its queryset'
        elif isinstance(target, forms.FileField):
            reason = 'a file is uploaded, not held as state'
        elif isinstance(target.widget, forms.PasswordInput) and not target.widget.render_value:
            reason = 'a write-only value is never signed or sent back'
        else:
            return
        message = f'A {type(target).__name__} cannot be held as state: {reason}.'
        raise GlueSerializerError(message)

    def load(self, raw: Any) -> Any:
        try:
            return self.target.clean(raw)
        except DjangoValidationError as error:
            raise GlueSerializerError(str(error)) from error

    def dump(self, value: Any) -> Any:
        return self.target.prepare_value(value)

    def adopt(self, value: Any) -> Any:
        """A default or an assigned value, cleaned as if the browser had sent it."""
        return self.load(self.dump(value))

    def presentation(
        self,
        *,
        read: Callable[[], Any],
        editable: bool,
    ) -> FieldAttributePresentation:
        _ = read
        return FieldAttributePresentation(field=self.target, editable=editable)


glue_serializer_registry.register(ModelFieldSerializer)
glue_serializer_registry.register(FormFieldSerializer)
glue_serializer_registry.register(FieldAttributeSerializer)
