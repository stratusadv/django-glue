from __future__ import annotations

from typing import Any, TYPE_CHECKING

from django_glue.access import GlueAccess
from django_glue.glue.attributes.base import BaseGlueAttribute

if TYPE_CHECKING:
    from django_glue.glue.base import BaseGlue


class ValueAttribute(BaseGlueAttribute):
    """
    An attribute that holds a value (not callable).

    The value may be a primitive, an object, or an object with its own
    nested Glue attributes that will be discovered and flattened into
    the parent GlueObject's attribute namespace.
    """

    def __init__(self, *, owner: BaseGlue, name: str, access: GlueAccess) -> None:
        super().__init__(owner=owner, name=name, access=access)

    @property
    def metadata(self) -> dict[str, Any]:
        return {'namespace': 'value'}
