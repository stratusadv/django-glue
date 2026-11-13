from __future__ import annotations

from typing import Any, TYPE_CHECKING

from django_glue.glue.attributes.attribute import (
    BoundGlueAttribute,
    GlueAttribute,
    GlueAttributeKind,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Mapping


class GlueAttributeRegistry:
    def __init__(
        self,
        attributes: Iterable[GlueAttribute],
        *,
        attribute_providers: Mapping[str, Any] | None = None,
    ) -> None:
        attributes = tuple(
            sorted(
                attributes,
                key=lambda attribute: attribute.path,
            )
        )
        self._validate(attributes)
        self._attributes = attributes
        self._attributes_by_path = {
            attribute.path: attribute
            for attribute in attributes
        }
        self._attribute_providers = dict(attribute_providers or {})

    @property
    def attributes(self) -> tuple[GlueAttribute, ...]:
        return self._attributes

    @staticmethod
    def _validate(attributes: tuple[GlueAttribute, ...]) -> None:
        paths = tuple(
            attribute.path
            for attribute in attributes
        )
        if paths != tuple(sorted(paths)):
            msg = 'Glue attributes must be ordered by path.'
            raise ValueError(msg)
        if len(paths) != len(set(paths)):
            msg = 'Glue attribute paths must be unique.'
            raise ValueError(msg)
        by_path = {
            attribute.path: attribute
            for attribute in attributes
        }
        for attribute in attributes:
            segments = attribute.path.split('.')
            for index in range(1, len(segments)):
                prefix = '.'.join(segments[:index])
                ancestor = by_path.get(prefix)
                if ancestor is None:
                    msg = (
                        f'Path {attribute.path!r} requires namespace prefix '
                        f'{prefix!r}.'
                    )
                    raise ValueError(msg)
                if ancestor.kind != GlueAttributeKind.NAMESPACE:
                    msg = (
                        f'Path {attribute.path!r} crosses non-namespace prefix '
                        f'{prefix!r}.'
                    )
                    raise ValueError(msg)

    def __iter__(self) -> Iterator[GlueAttribute]:
        return iter(self.attributes)

    def __len__(self) -> int:
        return len(self.attributes)

    def get(self, path: str) -> GlueAttribute | None:
        return self._attributes_by_path.get(path)

    def bind(self, owner: Any) -> tuple[BoundGlueAttribute, ...]:
        return tuple(
            BoundGlueAttribute(
                attribute=attribute,
                owner=owner,
                provider=self._attribute_providers.get(attribute.path),
            )
            for attribute in self.attributes
        )
