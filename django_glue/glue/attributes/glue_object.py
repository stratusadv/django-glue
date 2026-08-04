from __future__ import annotations

from typing import Any, TYPE_CHECKING

from django_glue.glue.attributes.base import BaseGlueAttribute

if TYPE_CHECKING:
    from django_glue.access import GlueAccess
    from django_glue.glue.base import BaseGlue


class GlueObjectAttribute(BaseGlueAttribute):
    def __init__(
        self,
        *,
        owner: BaseGlue,
        name: str,
        access: GlueAccess,
        glue_object: BaseGlue,
        attr_owner_instance: Any = None,
    ) -> None:
        super().__init__(
            owner=owner,
            name=name,
            access=access,
            attr_owner_instance=attr_owner_instance,
        )
        self.glue_object = glue_object

    def _prepare_glue_object(self) -> BaseGlue:
        self.glue_object.request = self.owner.request
        return self.glue_object

    @property
    def metadata(self) -> dict[str, Any]:
        glue_object = self._prepare_glue_object()
        return super().metadata | {
            'namespace': 'glue',
            'glue_namespace': glue_object.namespace,
            'metadata': glue_object.metadata,
        }

    @property
    def state(self) -> dict[str, Any] | None:
        return self._prepare_glue_object().state
