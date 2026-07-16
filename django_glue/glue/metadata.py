from __future__ import annotations

from typing import Any

from pydantic import RootModel


class GlueMetadata(RootModel[Any]):
    """Frontend-only metadata for a glued object.

    The shape is owned by the adapter for the object being glued.
    """

    @classmethod
    def from_payload(cls, data: Any) -> GlueMetadata:
        return cls.model_validate(data)

    def to_payload(self) -> Any:
        return self.root
