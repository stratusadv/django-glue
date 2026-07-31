from __future__ import annotations

from typing import Any

from django_glue.glue.attributes.state import StateAttribute


class CompositeStateAttribute(StateAttribute):
    """
    A state attribute that contains nested Glue attributes.

    Used for objects with @DeclaredAttribute-decorated members that are
    exposed as a group under a common namespace (e.g., 'stats.score', 'stats.reset').
    """

    def get(self) -> Any:
        composite_object = super().get()

        # TODO: Composite attributes currently don't expose state
        # but this is something that needs to be addressed in the future
        # potentially in the impending attribute/object unification refactor
        return {}

    @property
    def metadata(self) -> dict[str, Any]:
        return super().metadata | {'namespace': 'composite'}
