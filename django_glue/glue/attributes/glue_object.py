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
        target: Any = None,
    ) -> None:
        super().__init__(owner=owner, name=name, access=access, target=target)
        self.glue_object = glue_object

    def _prepare_glue_object(self) -> BaseGlue:
        self.glue_object.request = self.owner.request
        return self.glue_object

    @property
    def metadata(self) -> dict[str, Any]:
        glue_object = self._prepare_glue_object()
        return super().metadata | {
            'namespace': 'glue',
            'policy': glue_object.policy.model_dump(),
            'metadata': glue_object.metadata.to_payload(),
        }

    @property
    def state(self) -> dict[str, Any]:
        return self._prepare_glue_object().state
