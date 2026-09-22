from __future__ import annotations

import re
from typing import TYPE_CHECKING

from django_glue.exceptions import GlueComponentRegistrationError

if TYPE_CHECKING:
    from django_glue.glue.component.object import Component

_CAMEL_BOUNDARY = re.compile(r'(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])')

TAG_NAME_PATTERN = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*(?:\.[a-z0-9]+(?:-[a-z0-9]+)*)*$')


def derive_tag_name(component_class: type) -> str:
    """Derive the default public tag name from a class name.

    ``TimeEntryDay`` becomes ``time-entry-day``.
    """
    return _CAMEL_BOUNDARY.sub('-', component_class.__name__).lower()


class GlueComponentRegistry:
    """Resolves a signed tag name to its component class.

    Reconstruction reads ``identity['tag_name']`` and looks it up here rather
    than importing a signed path, so an unregistered name fails closed.

    Duplicate tag names are recorded rather than raised, and reported by the
    Django system check. Raising at import time would make the failure depend
    on import order, which is the behaviour the check exists to replace.
    """

    def __init__(self) -> None:
        self._components: dict[str, type[Component]] = {}
        self.collisions: list[tuple[str, str, str]] = []

    def register(self, component_class: type[Component], tag_name: str) -> None:
        existing = self._components.get(tag_name)

        if existing is not None and self._identifier(existing) != self._identifier(component_class):
            self.collisions.append((
                tag_name,
                self._identifier(existing),
                self._identifier(component_class),
            ))
            return

        self._components[tag_name] = component_class

    def get(self, tag_name: str) -> type[Component]:
        component_class = self._components.get(tag_name)

        if component_class is None:
            msg = (
                f"No Glue component is registered for tag name '{tag_name}'. "
                f'Registered: {sorted(self._components) or "none"}.'
            )
            raise GlueComponentRegistrationError(msg)

        return component_class

    def __contains__(self, tag_name: str) -> bool:
        return tag_name in self._components

    def __iter__(self):
        return iter(self._components.items())

    @staticmethod
    def _identifier(component_class: type) -> str:
        return f'{component_class.__module__}.{component_class.__qualname__}'


glue_component_registry = GlueComponentRegistry()
