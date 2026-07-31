from __future__ import annotations

from django_glue.glue.attributes.django.model.field import ModelFieldAttribute


class ManyToManyFieldAttribute(ModelFieldAttribute):
    """GlueAttribute for Django ManyToManyField relationships.

    TODO: This is a stub for future M2M support. The goal is to expose M2M
    relationships as nested QuerySetGlue objects, enabling frontend traversal
    and editing of related object sets.

    Currently, M2M fields are handled by ModelFieldAttribute.get() which
    serializes them as a list of {pk, __str__} dicts. This attribute will
    provide richer functionality including:
        - Nested QuerySetGlue for the related objects
        - Add/remove operations
        - Prefetch support via prefetch_related
    """
