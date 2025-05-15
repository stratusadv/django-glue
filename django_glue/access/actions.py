from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django_glue.access.access import Access


class BaseAction(str, Enum):
    def __str__(self) -> str:
        return self.value

    def required_access(self) -> Access:
        message = 'You must override required access on Glue Actions'
        raise NotImplementedError(message)
