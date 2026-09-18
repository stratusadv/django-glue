from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any


class GlueAttributeAdapter(ABC):
    @abstractmethod
    def schema(self) -> Mapping[str, Any]:
        raise NotImplementedError

    def unsigned_data(self) -> Mapping[str, Any]:
        return {}
