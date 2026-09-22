from __future__ import annotations

from abc import abstractmethod
from functools import cached_property
from typing import TYPE_CHECKING

from django_glue.glue import address
from django_glue.glue.base import BaseGlue
from django_glue.glue.children import BoundGlueChild
from django_glue.glue.operation import GlueOperation, GlueOperationKind

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping


class BaseCollectionGlue(BaseGlue):
    """A Glue object whose children are keyed items owned by the collection.

    The collection owns item-key derivation end to end (ADR 011); each leaf
    family yields its items via ``get_keyed_items()``. The children map is
    built from those items, so a collection's children are addressed by their
    declared key rather than by a fixed named attribute.
    """

    @abstractmethod
    def get_keyed_items(self) -> list[tuple[str, BaseGlue]]:
        """Yield this collection's items as (key, child) pairs."""
        raise NotImplementedError

    def _assert_identity(self) -> None:
        if not self.get_identity():
            msg = (
                f"Collection '{self.name}' has an empty identity; "
                'a collection identity cannot be empty.'
            )
            raise ValueError(msg)

    @cached_property
    def _bound_children(self) -> tuple[BoundGlueChild, ...]:
        return self._bind_children()

    def _bind_children(
        self,
        *,
        live_children: Mapping[str, str] | None = None,
        reintroduce: Iterable[str] = (),
    ) -> tuple[BoundGlueChild, ...]:
        _ = live_children, reintroduce
        if not self.is_bound:
            msg = f"Cannot bind children for unbound Glue object '{self.name}'."
            raise RuntimeError(msg)

        self._assert_identity()
        owner_address = self.address
        children: list[BoundGlueChild] = []
        for key, child in self.get_keyed_items():
            if not child.authorize(
                self.request,
                GlueOperation(
                    kind=GlueOperationKind.INTRODUCE,
                    attribute=None,
                    required_access=child.access,
                ),
            ):
                continue
            child.request = self.request
            children.append(
                BoundGlueChild(
                    path=key,
                    address=address.item(owner_address, key),
                    glue_object=child,
                )
            )
        return tuple(children)
