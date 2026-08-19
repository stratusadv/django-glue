from __future__ import annotations

from typing import Any, TYPE_CHECKING

from django_glue.access import GlueAccess
from django_glue.glue.attributes.declared import DeclaredAttribute
from django_glue.glue.base import BaseGlue
from django_glue.glue.loading import LoadingStrategy

if TYPE_CHECKING:
    from django_glue.glue.policy import GluePolicy


class CollectionLazyLoadNotSupportedError(NotImplementedError):
    """Raised when load_state is called on a lazily reconstructed collection."""

    def __init__(self, name: str) -> None:
        super().__init__(
            f"Collection '{name}' was reconstructed from policy without its original items. "
            "Lazy loading of collections is not yet supported. "
            "Use loading_strategy=LoadingStrategy.EAGER to include collection state in the initial manifest."
        )


class CollectionGlue(BaseGlue):
    """A list of independent Glue objects.

    Items are serialized as an ``items`` array of complete manifests (each
    with its own policy token, keyed by the item's own identity) rather than
    as individually named nested attributes. A collection's items are added,
    removed, and reordered as a unit -- there's no fixed, named set of
    sub-attributes the way a single object's fields are -- so they're
    represented client-side the same way any other list of glue objects
    returned from a call result is, not through the attribute-path system
    built for a single object's fixed shape.
    """

    namespace = 'collection'

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
        """Return collection state, or raise if lazily reconstructed.

        Collections reconstructed from policy have no items and cannot
        meaningfully load state. Use eager loading to include collection
        data in the initial manifest.
        """
        if self._reconstructed and not self.items:
            raise CollectionLazyLoadNotSupportedError(self.name)
        return self.state

    @classmethod
    def _reconstruct_from_policy(cls, policy: GluePolicy) -> CollectionGlue:
        return cls(
            [],
            name=policy.name,
            access=policy.access,
            _reconstructed=True,
        )
