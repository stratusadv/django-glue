from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    from django_glue.resolver.attribute_event.schemas import BoundProxyAttributeEvent


class BaseProxyState(ABC):
    """Abstract base class for all proxy state classes."""

    namespace: str = ''

    @abstractmethod
    def serialize(self) -> dict:
        ...

    @classmethod
    @abstractmethod
    def deserialize(cls, event: BoundProxyAttributeEvent) -> Self:
        ...
