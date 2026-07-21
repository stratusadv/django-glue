from __future__ import annotations

from typing import TYPE_CHECKING

from django.http import JsonResponse

from django_glue.encoders import GlueResponseJSONEncoder
from django_glue.glue.registry import glue_object_resolver_registry

if TYPE_CHECKING:
    from django_glue.glue.base import BaseGlue
    from django_glue.glue.schemas import AttributeCallResolverContext


class AttributeCallResolver:
    """Resolve an adapter-backed Glue attribute request."""

    def __init__(self, context: AttributeCallResolverContext) -> None:
        self.context = context

    def resolve(self) -> JsonResponse:
        glue_object_class: type[BaseGlue] = glue_object_resolver_registry.get_class_for_namespace(
            self.context.target_glue_policy.namespace
        )

        glue_object = glue_object_class.from_attribute_call_resolver_context(self.context)

        result = glue_object.process_attribute_call(self.context)

        return JsonResponse(
            **result,
            safe=True,
            encoder=GlueResponseJSONEncoder,
        )
