from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, TYPE_CHECKING

from django_glue.access import GlueAccess
from django_glue.utils import get_attr_from_path_string_on_instance

if TYPE_CHECKING:
    from django_glue.glue.base import BaseGlue


class BaseGlueAttribute(ABC):
    """
    Base class for all Glue attributes.

    Attributes represent named access points on a Glue object - either readable
    state (StateAttribute) or callable methods (CallableAttribute). The name
    is a dotted path from the owner GlueObject to the attribute.
    """

    def __init__(
        self,
        *,
        owner: BaseGlue,
        name: str,
        access: GlueAccess,
        attr_owner_instance: Any = None,
    ) -> None:
        self.owner = owner
        self.name = name
        self.required_access = access
        self._attr_owner_instance = attr_owner_instance

    @property
    @abstractmethod
    def metadata(self) -> dict[str, Any]:
        return {
            'name': self.name,
        }

    def get(self) -> Any:
        """Get the value at this attribute's path from the owner or attr_owner_instance."""
        resolve_from = self._attr_owner_instance if self._attr_owner_instance is not None else self.owner
        return get_attr_from_path_string_on_instance(resolve_from, self.name)