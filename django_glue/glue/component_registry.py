from __future__ import annotations

import re
from typing import TYPE_CHECKING

from django.core.checks import Error

from django_glue.exceptions import GlueComponentRegistrationError

if TYPE_CHECKING:
    from django_glue.glue.component import Component


TAG_NAME_PATTERN = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*(?:\.[a-z0-9]+(?:-[a-z0-9]+)*)*$')
CAMEL_BOUNDARY = re.compile(r'(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])')


class ComponentRegistry:
    def __init__(self) -> None:
        self.by_identifier: dict[str, type[Component]] = {}
        self.by_tag_name: dict[str, type[Component]] = {}
        self.collisions: list[tuple[str, str, str]] = []

    def register(self, component_class: type[Component]) -> None:
        identifier = f'{component_class.__module__}.{component_class.__qualname__}'
        tag_name = component_class.tag_name
        if tag_name is None or not TAG_NAME_PATTERN.fullmatch(tag_name):
            raise GlueComponentRegistrationError(f'Invalid Glue component tag name: {tag_name!r}')
        existing = self.by_tag_name.get(tag_name)
        if existing is not None and (
            f'{existing.__module__}.{existing.__qualname__}' != identifier
        ):
            existing_identifier = f'{existing.__module__}.{existing.__qualname__}'
            self.collisions.append((tag_name, existing_identifier, identifier))
        else:
            self.by_tag_name[tag_name] = component_class
        self.by_identifier[identifier] = component_class

    def from_tag_name(self, tag_name: str) -> type[Component]:
        try:
            return self.by_tag_name[tag_name]
        except KeyError as error:
            raise GlueComponentRegistrationError(f'Unknown Glue component tag name: {tag_name!r}') from error

    def from_identifier(self, identifier: str) -> type[Component]:
        try:
            return self.by_identifier[identifier]
        except KeyError as error:
            raise GlueComponentRegistrationError(f'Unknown Glue component identifier: {identifier!r}') from error


component_registry = ComponentRegistry()


def check_component_tag_names(app_configs: object = None, **kwargs: object) -> list[Error]:
    _ = app_configs, kwargs
    return [
        Error(
            f'Two Glue components claim tag name {tag_name!r}.',
            hint=f'{existing} and {duplicate} both resolve to it.',
            id='django_glue.E001',
        )
        for tag_name, existing, duplicate in component_registry.collisions
    ]
