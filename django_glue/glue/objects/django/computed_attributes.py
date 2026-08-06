from __future__ import annotations

import inspect
from functools import cached_property
from typing import Any, Callable, Mapping, TYPE_CHECKING

from django_glue.utils import get_attr_from_path_string

if TYPE_CHECKING:
    from django.db import models


ComputedAttribute = (
    str
    | Callable[['models.Model'], Any]
    | tuple[str | Callable[['models.Model'], Any], Mapping[str, Any]]
    | dict[str, Any]
)


class GlueComputedAttributesMixin:
    computed_attributes: dict[str, dict[str, Any]]

    def initialize_computed_attributes(
        self,
        computed_attributes: Mapping[str, ComputedAttribute] | None = None,
    ) -> None:
        self.computed_attributes = {
            name: self._normalize_computed_attribute(attribute)
            for name, attribute in (computed_attributes or {}).items()
        }

    def computed_attributes_identity(self) -> dict[str, Any]:
        if not self.computed_attributes:
            return {}
        return {'computed_attributes': self.computed_attributes}

    @cached_property
    def _computed_attribute_names(self) -> tuple[str, ...]:
        return tuple(self.computed_attributes)

    def computed_attribute_values(self, instance: models.Model) -> dict[str, Any]:
        values = {}
        for name, attribute in self.computed_attributes.items():
            attribute_path = attribute['path']
            kwargs = attribute.get('kwargs', {})
            values[name] = get_attr_from_path_string(attribute_path)(instance, **kwargs)
        return values

    def hydrate_computed_attributes(self, instance: models.Model) -> None:
        for name, value in self.computed_attribute_values(instance).items():
            setattr(instance, name, value)

    def _normalize_computed_attribute(self, attribute: ComputedAttribute) -> dict[str, Any]:
        if isinstance(attribute, dict):
            return {
                'path': attribute['path'],
                'kwargs': attribute.get('kwargs', {}),
            }

        kwargs = {}
        callable_or_path = attribute
        if isinstance(attribute, tuple):
            callable_or_path, kwargs = attribute

        if isinstance(callable_or_path, str):
            return {'path': callable_or_path, 'kwargs': dict(kwargs)}

        unwrapped = inspect.unwrap(callable_or_path)
        if '<locals>' in unwrapped.__qualname__ or unwrapped.__qualname__ != unwrapped.__name__:
            msg = (
                f'{self.__class__.__name__} computed attributes must be importable '
                'top-level callables.'
            )
            raise ValueError(msg)
        return {
            'path': f'{unwrapped.__module__}.{unwrapped.__qualname__}',
            'kwargs': dict(kwargs),
        }
