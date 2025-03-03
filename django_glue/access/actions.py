from __future__ import annotations

from abc import ABC
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django_glue.access.access import Access


class BaseAction(str, Enum, ABC):

    def __str__(self) -> str:
        return self.value

    def required_access(self) -> Access:
        raise NotImplemented('You must override required access on Glue Actions')