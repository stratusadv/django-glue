from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from django_glue.glue import address
from django_glue.glue.attributes.definition import GlueAttributeKind
from django_glue.glue.operation import GlueOperation, GlueOperationKind

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from django_glue.glue.attributes.definition import BoundGlueAttribute
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
            for attribute in self.attribute_registry.bind(self.owner)
            if attribute.definition.kind == GlueAttributeKind.CHILD
            for child in self._bind_attribute(
                attribute,
                live_address=live_children.get(attribute.definition.path),
                reintroduce=attribute.definition.path in reintroduce,
            )
        )

    def _bind_attribute(
        self,
        attribute: BoundGlueAttribute,
        *,
        live_address: str | None,
        reintroduce: bool,
    ) -> tuple[BoundGlueChild, ...]:
        definition = attribute.definition
        if live_address is not None and not definition.is_nullable and not reintroduce:
            return (
                BoundGlueChild(
                    path=definition.path,
                    address=live_address,
                ),
            )

        glue_object = attribute.resolve_child()
        if glue_object is None:
            return ()

        resolved_address = address.child(
            owner_address=self.owner.address,
            path=definition.path,
        )
        if live_address == resolved_address and not reintroduce:
            return (
                BoundGlueChild(
                    path=definition.path,
                    address=resolved_address,
                ),
            )

        request = self.owner.request
        if not glue_object.authorize(
            request,
            GlueOperation(
                kind=GlueOperationKind.INTRODUCE,
                attribute=None,
                required_access=glue_object.access,
            ),
        ):
            return ()

        glue_object.request = request
        return (
            BoundGlueChild(
                path=definition.path,
                address=live_address if reintroduce and live_address else resolved_address,
                glue_object=glue_object,
            ),
        )
