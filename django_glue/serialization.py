from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from django import forms
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models
from pydantic import TypeAdapter
from pydantic import ValidationError as PydanticValidationError

if TYPE_CHECKING:
    from collections.abc import Iterable


class GlueSerializerError(ValueError):
    pass


class GlueSerializerHandler(ABC):
    @abstractmethod
    def supports(self, target: Any) -> bool:
        raise NotImplementedError

    @abstractmethod
    def coerce(self, value: Any, target: Any) -> Any:
        raise NotImplementedError

    @abstractmethod
    def decode(self, value: Any, target: Any) -> Any:
        raise NotImplementedError


class GlueSerializerRegistry:
    def __init__(
        self,
        handlers: Iterable[GlueSerializerHandler] = (),
    ) -> None:
        self._handlers = list(handlers)

    def register(
        self,
        handler: GlueSerializerHandler,
        *,
        prepend: bool = True,
    ) -> GlueSerializerHandler:
        if prepend:
            self._handlers.insert(0, handler)
        else:
            self._handlers.append(handler)
        return handler

    def coerce(
        self,
        value: Any,
        target: Any,
    ) -> Any:
        for handler in self._handlers:
            if handler.supports(target):
                return handler.coerce(value, target)
        return value

    def decode(
        self,
        value: Any,
        target: Any,
    ) -> Any:
        for handler in self._handlers:
            if handler.supports(target):
                return handler.decode(value, target)
        return value


class DjangoModelFieldSerializer(GlueSerializerHandler):
    def supports(self, target: Any) -> bool:
        return isinstance(target, models.Field)

    def coerce(self, value: Any, target: models.Field) -> Any:
        try:
            if isinstance(target, models.FileField):
                message = 'File fields are uploaded, not updated as values.'
                raise GlueSerializerError(message)
            if isinstance(target, models.JSONField):
                return value
            if getattr(target, 'many_to_many', False):
                if value is not None and (
                    not isinstance(value, (list, tuple))
                    or any(isinstance(item, dict) for item in value)
                ):
                    message = 'Membership updates must be a flat list of identities.'
                    raise GlueSerializerError(message)
                return [
                    target.target_field.to_python(item)
                    for item in value or []
                ]
            if getattr(target, 'many_to_one', False) or getattr(target, 'one_to_one', False):
                if isinstance(value, (dict, list, tuple)):
                    message = 'Relation updates must be a raw identity value.'
                    raise GlueSerializerError(message)
                return target.target_field.to_python(value)
            return target.to_python(value)
        except DjangoValidationError as error:
            raise GlueSerializerError(str(error)) from error

    def decode(self, value: Any, target: models.Field) -> Any:
        if isinstance(target, models.FileField):
            return value
        return self.coerce(value, target)


class DjangoFormFieldSerializer(GlueSerializerHandler):
    def supports(self, target: Any) -> bool:
        return isinstance(target, forms.Field)

    def coerce(self, value: Any, target: forms.Field) -> Any:
        if isinstance(target, forms.FileField):
            message = 'File fields are uploaded, not updated as values.'
            raise GlueSerializerError(message)
        if isinstance(target, forms.ModelMultipleChoiceField):
            if value is not None and (
                not isinstance(value, (list, tuple))
                or any(isinstance(item, dict) for item in value)
            ):
                message = 'Choice updates must be a flat list of values.'
                raise GlueSerializerError(message)
        elif isinstance(target, forms.ModelChoiceField) and isinstance(
            value,
            (dict, list, tuple),
        ):
            message = 'Choice updates must be a raw choice value.'
            raise GlueSerializerError(message)
        return value

    def decode(self, value: Any, target: forms.Field) -> Any:
        _ = target
        return value


class AnnotationSerializer(GlueSerializerHandler):
    def supports(self, target: Any) -> bool:
        return target is not None

    def coerce(self, value: Any, target: Any) -> Any:
        try:
            return TypeAdapter(target).validate_python(value)
        except (PydanticValidationError, TypeError, ValueError) as error:
            raise GlueSerializerError(str(error)) from error

    def decode(self, value: Any, target: Any) -> Any:
        return self.coerce(value, target)


glue_serializer_registry = GlueSerializerRegistry(
    (
        DjangoModelFieldSerializer(),
        DjangoFormFieldSerializer(),
        AnnotationSerializer(),
    )
)


__all__ = [
    'GlueSerializerError',
    'GlueSerializerHandler',
    'GlueSerializerRegistry',
    'glue_serializer_registry',
]
