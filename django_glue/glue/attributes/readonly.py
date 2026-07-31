from __future__ import annotations

from typing import Any

from django_glue.glue.attributes.state import StateAttribute


class ReadOnlyAttribute(StateAttribute):
    """
    A state attribute that is read-only regardless of the GlueObject's access level.

    Used for computed values like properties and queryset annotations that
    cannot be written back to the backend.
    """

    @property
    def metadata(self) -> dict[str, Any]:
        return super().metadata | {'namespace': 'readonly'}
