from __future__ import annotations

from typing import Any

from django_glue.proxies.state import BaseProxyState


class GlueTemplateProxyState(BaseProxyState):
    """State for a template proxy — holds template path and context data."""

    namespace = 'template'

    def __init__(self, template_path: str, context_data: dict[str, Any] | None = None) -> None:
        self.template_path = template_path
        self.context_data = context_data or {}

    def serialize(self) -> dict:
        return {
            'namespace': self.namespace,
            'context_data': self.context_data,
        }

    @classmethod
    def deserialize(cls, event: BoundProxyAttributeEvent) -> GlueTemplateProxyState:  # type: ignore[name-defined] # noqa: F821
        subject_details = event.policy.subject_details
        return cls(
            template_path=subject_details.template_path,
            context_data=subject_details.initial_context_data,
        )
