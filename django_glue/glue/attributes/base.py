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
    values (ValueAttribute) or callable methods (CallableAttribute). The name
    is a dotted path from the owner GlueObject to the attribute.
    """

    def __init__(self, *, owner: BaseGlue, name: str, access: GlueAccess) -> None:
        self.owner = owner
        self.name = name
        self.required_access = access

    @property
    @abstractmethod
    def metadata(self) -> dict[str, Any]:
        raise NotImplementedError

    def get(self) -> Any:
        """Get the target at this attribute's path from the owner."""
        return get_attr_from_path_string_on_instance(self.owner, self.name)
