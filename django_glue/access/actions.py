from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from django_glue.access.access import Access


class BaseGlueActionType(str, Enum):
    def __str__(self) -> str:
        return self.value

    def required_access(self) -> Access:
        raise NotImplemented('You must override required access on Glue Actions')


class GlueAction(BaseModel):
    action: BaseGlueActionType
    data: dict