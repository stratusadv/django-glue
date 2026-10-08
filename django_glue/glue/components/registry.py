from __future__ import annotations

import importlib
import re
from typing import TYPE_CHECKING

from django_glue.exceptions import GlueComponentRegistrationError
from django_glue.glue.components.discovery import resolve_component

if TYPE_CHECKING:
    from django_glue.glue.components.component import Component


TAG_NAME_PATTERN = re.compile(r'^[a-z0-9]+(?:_[a-z0-9]+)*(?:/[a-z0-9]+(?:_[a-z0-9]+)*)*$')
CAMEL_BOUNDARY = re.compile(r'(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])')


class ComponentRegistry:
    """A cache of resolved component classes, populated lazily.

    Components are found by their template tag (``from_tag_name``) or their
    signed ``module.qualname`` identity (``from_identifier``); both resolve on
    demand and memoize. Nothing here is populated at startup.
    """

    def __init__(self) -> None:
        self.by_identifier: dict[str, type[Component]] = {}
        self.by_tag_name: dict[str, type[Component]] = {}

    def register(self, component_class: type[Component]) -> None:
        """Pre-warm the identifier cache so reconstruction by the signed
        ``component_id`` is a lookup rather than an import. Never a precondition
        for a tag to resolve."""
        self.by_identifier[f'{component_class.__module__}.{component_class.__qualname__}'] = component_class

    def from_tag_name(self, tag_name: str) -> type[Component]:
        resolved = self.by_tag_name.get(tag_name)
        if resolved is not None:
            return resolved
        if not TAG_NAME_PATTERN.fullmatch(tag_name):
            raise GlueComponentRegistrationError(f'Invalid Glue component tag name: {tag_name!r}')
        component_class = resolve_component(tag_name)
        self.by_tag_name[tag_name] = component_class
        self.register(component_class)
        return component_class

    def from_identifier(self, identifier: str) -> type[Component]:
        resolved = self.by_identifier.get(identifier)
        if resolved is not None:
            return resolved
        module_name, _, qualname = identifier.rpartition('.')
        try:
            component_class: object = importlib.import_module(module_name)
            for part in qualname.split('.'):
                component_class = getattr(component_class, part)
        except (ModuleNotFoundError, AttributeError) as error:
            raise GlueComponentRegistrationError(
                f'Unknown Glue component identifier: {identifier!r}',
            ) from error
        self.by_identifier[identifier] = component_class  # type: ignore[assignment]
        return component_class  # type: ignore[return-value]


component_registry = ComponentRegistry()
