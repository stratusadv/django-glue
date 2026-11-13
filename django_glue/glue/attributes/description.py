from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any


class GlueFieldDescription(ABC):
    """
    What the browser needs to draw a control for one value attribute.

    ``schema()`` is the stable client-visible interface (state-model.md §4,
    §10): it ships in the ``schema`` channel and is omitted when unchanged.
    ``computed_data()`` is the complete current state-dependent output and
    ships in ``computed_data.fields``. The description owns what its output
    contains (a field's includes the current selection and its validation
    errors), and base only decides whether it re-derived this request.

    A description converts nothing: the attribute's serializer does that.
    """

    @abstractmethod
    def schema(self) -> Mapping[str, Any]:
        raise NotImplementedError

    def computed_data(self) -> Mapping[str, Any]:
        return {}
