from __future__ import annotations

from abc import abstractmethod
from functools import cached_property
from typing import TYPE_CHECKING, ClassVar

from django_glue.exceptions import GlueAuthorizationError
from django_glue.glue import address
from django_glue.glue.base import BaseGlue
from django_glue.glue.children import BoundGlueChild

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from django_glue.glue.policy import GluePolicy


class BaseCollectionGlue(BaseGlue):
    """A Glue object whose children are keyed items owned by the collection.

    The collection owns item-key derivation end to end (ADR 011); each leaf
    family yields its items via ``get_keyed_items()``. The children map is
    built from those items, so a collection's children are addressed by their
    declared key rather than by a fixed named attribute.
    """

    rebuilds_items: ClassVar[bool] = True

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

    def _membership(
        self,
        live_children: Mapping[str, str],
        produced: Mapping[str, BaseGlue],
    ) -> list[str]:
        """The keys the successor ``children`` map binds. By default the items
        produced this request are the whole membership."""
        _ = live_children
        return list(produced)

    def _rebuild_item(self, key: str) -> BaseGlue | None:
        """Re-run the item factory for a live key named in ``reintroduce``;
        None when the item no longer exists."""
        _ = key
        return None

    def _admit_reintroduce(self, policy: GluePolicy, reintroduce: list[str]) -> None:
        """A live item key is reintroducible when this family can rebuild its
        items (state-model.md §10 slot table, row 4)."""
        live_keys = set(policy.children) if self.rebuilds_items else set()
        super()._admit_reintroduce(policy, [path for path in reintroduce if path not in live_keys])

    def _bind_children(
        self,
        *,
        live_children: Mapping[str, str] | None = None,
        reintroduce: Iterable[str] = (),
    ) -> tuple[BoundGlueChild, ...]:
        """Produced items introduce at their keyed addresses; a live member not
        produced this request carries forward by address without running its
        factory, unless ``reintroduce`` names it (state-model.md §10 slot
        table, rows 2 and 4)."""
        if not self.is_bound:
            msg = f"Cannot bind children for unbound Glue object '{self.name}'."
            raise RuntimeError(msg)

        self._assert_identity()
        live_children = dict(live_children or {})
        reintroduce = set(reintroduce)
        produced = dict(self.get_keyed_items())
        owner_address = self.address
        children: list[BoundGlueChild] = []
        for key in self._membership(live_children, produced):
            child = produced.get(key)
            if child is None and key in reintroduce:
                child = self._rebuild_item(key)
                if child is None:
                    continue
            if child is None:
                children.append(BoundGlueChild(path=key, address=live_children[key]))
                continue
            try:
                child.introduce(self.request)
            except GlueAuthorizationError:
                continue
            children.append(
                BoundGlueChild(
                    path=key,
                    address=address.item(owner_address, key),
                    glue_object=child,
                )
            )
        return tuple(children)
