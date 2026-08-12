from __future__ import annotations

from functools import cached_property
from typing import Any, TYPE_CHECKING

from django_glue.access import GlueAccess
from django_glue.glue.attributes.declared import DeclaredAttribute
from django_glue.glue.attributes.glue_object import GlueObjectAttribute
from django_glue.glue.base import BaseGlue
from django_glue.glue.loading import LoadingStrategy

if TYPE_CHECKING:
    from django_glue.glue.attributes import BaseGlueAttribute
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

    @cached_property
    def attributes(self) -> dict[str, BaseGlueAttribute]:
        return {
            f'items.{index}': GlueObjectAttribute(
                owner=self,
                name=f'items.{index}',
                access=self.access,
                glue_object=item,
            )
            for index, item in enumerate(self.items)
        }

    @DeclaredAttribute(access=GlueAccess.VIEW, takes_client_state=False)
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
