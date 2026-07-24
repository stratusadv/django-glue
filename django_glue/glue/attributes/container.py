from __future__ import annotations

from typing import Any, TYPE_CHECKING

from django_glue.glue.attributes.base import BaseGlueAttribute

if TYPE_CHECKING:
    from django_glue.access import GlueAccess
    from django_glue.glue.base import BaseGlue


class ContainerAttribute(BaseGlueAttribute):
    """A non-state attribute that contains nested Glue attributes."""

    def __init__(
        self,
        *,
        owner: BaseGlue,
        name: str,
        access: GlueAccess,
        target: Any = None,
    ) -> None:
        super().__init__(
            owner=owner,
            name=name,
            access=access,
            target=target,
        )

    @property
    def metadata(self) -> dict[str, Any]:
        return super().metadata | {'namespace': 'container'}
