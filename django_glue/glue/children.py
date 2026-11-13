from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from django_glue.glue import address
from django_glue.glue.attributes.attribute import GlueAttributeKind
from django_glue.exceptions import GlueAuthorizationError

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from django_glue.glue.attributes.attribute import BoundGlueAttribute
    from django_glue.glue.attributes.registry import GlueAttributeRegistry
    from django_glue.glue.base import BaseGlue


@dataclass(frozen=True, slots=True, kw_only=True)
class BoundGlueChild:
    path: str
    address: str
    glue_object: BaseGlue | None = None


class GlueChildBinder:
    def __init__(
        self,
        owner: BaseGlue,
        attribute_registry: GlueAttributeRegistry,
    ) -> None:
        self.owner = owner
        self.attribute_registry = attribute_registry

    def bind(
        self,
        *,
        live_children: Mapping[str, str] | None = None,
        reintroduce: Iterable[str] = (),
    ) -> tuple[BoundGlueChild, ...]:
        if not self.owner.is_bound:
            msg = f"Cannot bind children for unbound Glue object '{self.owner.name}'."
            raise RuntimeError(msg)

        live_children = live_children or {}
        reintroduce = frozenset(reintroduce)
        return tuple(
            child
            for bound in self.attribute_registry.bind(self.owner)
            if bound.attribute.kind == GlueAttributeKind.CHILD
            for child in self._bind_attribute(
                bound,
                live_address=live_children.get(bound.attribute.path),
                reintroduce=bound.attribute.path in reintroduce,
            )
        )

    def _bind_attribute(
        self,
        bound: BoundGlueAttribute,
        *,
        live_address: str | None,
        reintroduce: bool,
    ) -> tuple[BoundGlueChild, ...]:
        attribute = bound.attribute
        if live_address is not None and not attribute.is_nullable and not reintroduce:
            return (
                BoundGlueChild(
                    path=attribute.path,
                    address=live_address,
                ),
            )

        glue_object = bound.resolve_child()
        if glue_object is None:
            return ()

        resolved_address = address.child(
            owner_address=self.owner.address,
            path=attribute.path,
        )
        if live_address == resolved_address and not reintroduce:
            return (
                BoundGlueChild(
                    path=attribute.path,
                    address=resolved_address,
                ),
            )

        try:
            glue_object.introduce(self.owner.request)
        except GlueAuthorizationError:
            return ()
        return (
            BoundGlueChild(
                path=attribute.path,
                address=live_address if reintroduce and live_address else resolved_address,
                glue_object=glue_object,
            ),
        )
