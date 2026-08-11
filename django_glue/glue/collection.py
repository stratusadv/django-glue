from __future__ import annotations

from functools import cached_property
from typing import TYPE_CHECKING

from django_glue.access import GlueAccess
from django_glue.glue.attributes.glue_object import GlueObjectAttribute
from django_glue.glue.base import BaseGlue

if TYPE_CHECKING:
    from django_glue.glue.attributes import BaseGlueAttribute
    from django_glue.glue.policy import GluePolicy


class CollectionGlue(BaseGlue):
    namespace = 'collection'

    def __init__(
        self,
        items: list[BaseGlue],
        *,
        name: str,
        access: GlueAccess = GlueAccess.VIEW,
    ) -> None:
        super().__init__(name=name, access=access)
        self.items = items

    @property
    def identity(self) -> dict:
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

    @classmethod
    def _reconstruct_from_policy(cls, policy: GluePolicy) -> CollectionGlue:
        return cls(
            [],
            name=policy.name,
            access=policy.access,
        )
