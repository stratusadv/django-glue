from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING, Type

from django_glue.glue.post_data import BaseActionKwargs

if TYPE_CHECKING:
    from django_glue.access.access import Access


class BaseAction(ABC, str, Enum):

    def __str__(self) -> str:
        return self.value

    @abstractmethod
    def required_access(self) -> Access:
        raise NotImplemented('You must override required access on Glue Actions')

    @abstractmethod
    @property
    def action_kwargs_type(self) -> Type[BaseActionKwargs]:
        raise NotImplemented('You must override action kwargs type on Glue Actions')