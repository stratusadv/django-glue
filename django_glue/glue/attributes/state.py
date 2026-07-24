from __future__ import annotations

from typing import Any, TYPE_CHECKING

from django_glue.access import GlueAccess
from django_glue.glue.attributes.base import BaseGlueAttribute

if TYPE_CHECKING:
    from django_glue.glue.base import BaseGlue


class StateAttribute(BaseGlueAttribute):
    """
    An attribute that holds state (not callable).

    State attributes have a value and can track errors. The value may be
    a primitive, an object, or an object with its own nested Glue attributes
    that will be discovered and flattened into the parent GlueObject's
    attribute namespace.
    """

    def __init__(
        self,
        *,
        owner: BaseGlue,
        name: str,
        access: GlueAccess,
        target: Any = None,
    ) -> None:
        super().__init__(owner=owner, name=name, access=access, target=target)

    @property
    def metadata(self) -> dict[str, Any]:
        return super().metadata | {'namespace': 'state'}

    @property
    def state(self) -> dict[str, Any]:
        return {}
