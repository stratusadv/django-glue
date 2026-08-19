from __future__ import annotations

from typing import Any, Callable, TYPE_CHECKING

from django_glue.access import GlueAccess
from django_glue.glue.attributes.declared import DeclaredAttribute
from django_glue.glue.base import BaseGlue
from django_glue.glue.loading import LoadingStrategy

if TYPE_CHECKING:
    from django_glue.glue.policy import GluePolicy


class SequenceLazyLoadNotSupportedError(NotImplementedError):
    """Raised when load_state is called on a lazily reconstructed sequence."""

    def __init__(self, name: str) -> None:
        super().__init__(
            f"Sequence '{name}' was reconstructed from policy without its original items. "
            "Lazy loading of sequences is not yet supported. "
            "Use loading_strategy=LoadingStrategy.EAGER to include sequence state in the initial manifest."
        )


class SequenceGlue(BaseGlue):
    """A list of independent Glue objects.

    Items are serialized as an ``items`` array of complete manifests (each
    with its own policy token, keyed by the item's own identity) rather than
    as individually named nested attributes. A sequence's items are added,
    removed, and reordered as a unit -- there's no fixed, named set of
    sub-attributes the way a single object's fields are -- so they're
    represented client-side the same way any other list of glue objects
    returned from a call result is, not through the attribute-path system
    built for a single object's fixed shape.
    """

    namespace = 'sequence'

    def __init__(
        self,
        items: list[BaseGlue],
        *,
        name: str,
        access: GlueAccess = GlueAccess.VIEW,
        loading_strategy: LoadingStrategy = LoadingStrategy.LAZY,
        _reconstructed: bool = False,
    ) -> None:
        super().__init__(name=name, access=access, loading_strategy=loading_strategy)
        self.items = items
        self._reconstructed = _reconstructed

    def get_identity(self) -> dict:
        return {}

    def get_state(self) -> dict[str, Any]:
        return {'items': [self._item_manifest(item) for item in self.items]}

    def get_metadata(self) -> dict[str, Any]:
        return {'attributes': {}}

    def _item_manifest(self, item: BaseGlue) -> dict[str, Any]:
        item.request = self.request
        return item.manifest.model_dump()

    @DeclaredAttribute(required_access=GlueAccess.VIEW, takes_client_state=False)
    def load_state(self) -> dict[str, Any]:
        """Return sequence state, or raise if lazily reconstructed.

        Sequences reconstructed from policy have no items and cannot
        meaningfully load state. Use eager loading to include sequence
        data in the initial manifest.
        """
        if self._reconstructed and not self.items:
            raise SequenceLazyLoadNotSupportedError(self.name)
        return self.state

    @classmethod
    def _reconstruct_from_policy(cls, policy: GluePolicy) -> SequenceGlue:
        return cls(
            [],
            name=policy.name,
            access=policy.access,
            _reconstructed=True,
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

        return cls(
            glued_items,
            name=name,
            access=access,
            loading_strategy=LoadingStrategy.EAGER,
        )

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
