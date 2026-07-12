from __future__ import annotations

from typing import Any

from django_glue.proxies.state import BaseProxyState


class GlueFunctionProxyState(BaseProxyState):
    """State for a function proxy — holds function path and previous kwargs."""

    namespace = 'function'

    def __init__(self, function_path: str, previous_kwargs: dict[str, Any] | None = None) -> None:
        self.function_path = function_path
        self.previous_kwargs = previous_kwargs

    def serialize(self) -> dict:
        return {
            'namespace': self.namespace,
            'previous_kwargs': self.previous_kwargs,
        }

    @classmethod
    def deserialize(cls, event: BoundProxyAttributeEvent) -> GlueFunctionProxyState:  # type: ignore[name-defined] # noqa: F821
        subject_details = event.policy.subject_details
        return cls(
            function_path=subject_details.function_path,
        )
