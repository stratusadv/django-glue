from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any


class GlueAttributeAdapter(ABC):
    """Leaf adapter for a projected value attribute.

    Splits the legacy mixed-grain ``state`` into its spec channels
    (state-model.md §4, §10): ``schema()`` is the stable client-visible
    interface (ships in the ``schema`` channel, omitted when unchanged);
    ``computed_data()`` is the adapter's complete current state-dependent
    output (ships in ``computed_data.fields``). The adapter owns what its
    output contains — e.g. field adapters include the current selection and
    their validation errors — and base only decides *whether* the adapter
    re-derived this request (omission is derived, not declared).
    """

    @abstractmethod
    def schema(self) -> Mapping[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def coerce(self, value: Any) -> Any:
        raise NotImplementedError

    @abstractmethod
    def decode(self, value: Any) -> Any:
        raise NotImplementedError

    def computed_data(self) -> Mapping[str, Any]:
        return {}
