from __future__ import annotations

from typing import Any

from django import forms
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models

from django_glue.serialization import GlueSerializer, GlueSerializerError, glue_serializer_registry


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
    """A form field's value, held raw for the form to clean: loading only refuses a wrong shape."""

    @classmethod
    def supports(cls, target: Any) -> bool:
        return isinstance(target, forms.Field)

    def load(self, raw: Any) -> Any:
        field = self.target
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


glue_serializer_registry.register(ModelFieldSerializer)
glue_serializer_registry.register(FormFieldSerializer)
