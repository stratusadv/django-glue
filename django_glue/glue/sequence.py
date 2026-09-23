from __future__ import annotations

from typing import Any, Callable, TYPE_CHECKING

from django_glue.access import GlueAccess
from django_glue.glue import address
from django_glue.glue.base import BaseGlue
from django_glue.glue.collection import BaseCollectionGlue

if TYPE_CHECKING:
    from collections.abc import Mapping

    from django_glue.glue.policy import GluePolicy


class SequenceGlue(BaseCollectionGlue):
    """A list of independent Glue objects.

    Items have independent addresses and entries in the shared object graph.
    """

    namespace = 'sequence'
    rebuilds_items = False

    def __init__(
        self,
        items: list[BaseGlue],
        *,
        name: str,
        access: GlueAccess = GlueAccess.VIEW,
        _item_keys: list[str] | None = None,
    ) -> None:
        super().__init__(name=name, access=access)
        self.items = items
        self._item_keys = _item_keys if _item_keys is not None else [item.name for item in items]

    def get_identity(self) -> dict[str, Any]:
        return {'item_keys': self._item_keys}

    def get_state(self) -> dict[str, Any]:
        return {
            'items': [address.item(self.address, item.name) for item in self.items],
        }

    def get_keyed_items(self) -> list[tuple[str, BaseGlue]]:
        return [(item.name, item) for item in self.items]

    def _membership(
        self,
        live_children: Mapping[str, str],
        produced: Mapping[str, BaseGlue],
    ) -> list[str]:
        """Signed ``item_keys``: items exist only in the render that built
        them, so live items carry forward by address."""
        return [key for key in self._item_keys if key in produced or key in live_children]

    @classmethod
    def _reconstruct_from_policy(cls, policy: GluePolicy) -> SequenceGlue:
        return cls(
            [],
            name=policy.name,
            access=policy.access,
            _item_keys=policy.identity['item_keys'],
        )

    @classmethod
    def from_item_factory(
        cls,
        items: list[Any],
        *,
        name: str,
        access: GlueAccess = GlueAccess.VIEW,
        glue_factory: Callable[..., BaseGlue] | None = None,
    ) -> SequenceGlue:
        """Build a SequenceGlue from a plain list of raw and/or already-glued items.

        Items that are already Glue objects are used as-is. Any other item is
        converted via glue_factory(item, *, name, access) -> BaseGlue; a raw
        item with no glue_factory raises TypeError.
        """
        glued_items = [
            item if isinstance(item, BaseGlue) else cls._build_item_from_factory(
                item, index, name=name, access=access, glue_factory=glue_factory,
            )
            for index, item in enumerate(items)
        ]

        return cls(glued_items, name=name, access=access)

    @staticmethod
    def _build_item_from_factory(
        item: Any,
        index: int,
        *,
        name: str,
        access: GlueAccess,
        glue_factory: Callable[..., BaseGlue] | None,
    ) -> BaseGlue:
        if glue_factory is None:
            msg = (
                f"Sequence '{name}' received a raw '{item.__class__.__name__}' item "
                'that is not a Glue object. Pass glue_factory=... to Glue.attr(...) to '
                'convert raw items into Glue objects automatically.'
            )
            raise TypeError(msg)

        return glue_factory(item, name=f'{name}.{index}', access=access)
