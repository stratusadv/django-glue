from __future__ import annotations

from typing import Any, TYPE_CHECKING

from django_glue.glue.attributes.definition import (
    BoundGlueAttribute,
    GlueAttributeDefinition,
    GlueAttributeKind,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Mapping


class GlueAttributeRegistry:
    def __init__(
        self,
        attribute_definitions: Iterable[GlueAttributeDefinition],
        *,
        attribute_providers: Mapping[str, Any] | None = None,
    ) -> None:
        attribute_definitions = tuple(
            sorted(
                attribute_definitions,
                key=lambda definition: definition.path,
            )
        )
        self._validate(attribute_definitions)
        self._attribute_definitions = attribute_definitions
        self._definitions_by_path = {
            definition.path: definition
            for definition in attribute_definitions
        }
        self._attribute_providers = dict(attribute_providers or {})

    @property
    def attribute_definitions(self) -> tuple[GlueAttributeDefinition, ...]:
        return self._attribute_definitions

    @staticmethod
    def _validate(attribute_definitions: tuple[GlueAttributeDefinition, ...]) -> None:
        paths = tuple(
            definition.path
            for definition in attribute_definitions
        )
        if paths != tuple(sorted(paths)):
            msg = 'Glue attribute definitions must be ordered by path.'
            raise ValueError(msg)
        if len(paths) != len(set(paths)):
            msg = 'Glue attribute definition paths must be unique.'
            raise ValueError(msg)
        by_path = {
            definition.path: definition
            for definition in attribute_definitions
        }
        for definition in attribute_definitions:
            segments = definition.path.split('.')
            for index in range(1, len(segments)):
                prefix = '.'.join(segments[:index])
                ancestor = by_path.get(prefix)
                if ancestor is None:
                    msg = (
                        f'Path {definition.path!r} requires namespace prefix '
                        f'{prefix!r}.'
                    )
                    raise ValueError(msg)
                if ancestor.kind != GlueAttributeKind.NAMESPACE:
                    msg = (
                        f'Path {definition.path!r} crosses non-namespace prefix '
                        f'{prefix!r}.'
                    )
                    raise ValueError(msg)

    def __iter__(self) -> Iterator[GlueAttributeDefinition]:
        return iter(self.attribute_definitions)

    def __len__(self) -> int:
        return len(self.attribute_definitions)

    def get(self, path: str) -> GlueAttributeDefinition | None:
        return self._definitions_by_path.get(path)

    def bind(self, owner: Any) -> tuple[BoundGlueAttribute, ...]:
        return tuple(
            BoundGlueAttribute(
                definition=definition,
                owner=owner,
                provider=self._attribute_providers.get(definition.path),
            )
            for definition in self.attribute_definitions
        )
