from __future__ import annotations

from typing import Any

from django.core.checks import Error

from django_glue.glue.component.registry import glue_component_registry

DUPLICATE_TAG_NAME = 'django_glue.E001'


def check_component_tag_names(app_configs: Any = None, **kwargs: Any) -> list[Error]:
    """Report component classes claiming the same public tag name.

    Registration records collisions instead of raising so the failure does not
    depend on import order; this check turns them into a startup error.
    """
    _ = app_configs, kwargs

    return [
        Error(
            f"Two Glue components claim the tag name '{tag_name}'.",
            hint=(
                f'{existing} and {duplicate} both resolve to it. '
                f'Set an explicit tag_name on one of them.'
            ),
            id=DUPLICATE_TAG_NAME,
        )
        for tag_name, existing, duplicate in glue_component_registry.collisions
    ]
