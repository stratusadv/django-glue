from __future__ import annotations

from typing import TYPE_CHECKING

from django_glue.glue.registry import glue_class_registry
from django_glue.resolver.attribute_call.context import (
    AttributeCallContextFactory,
    AttributeCallRequestContext,
)
from django_glue.resolver.base import GlueResolver

if TYPE_CHECKING:
    from django.http import JsonResponse
    from django.http import HttpRequest


class GlueAttributeCallResolver(GlueResolver[AttributeCallRequestContext]):
    def _create_context_from_request(
        self,
        request: HttpRequest,
    ) -> AttributeCallRequestContext:
        return AttributeCallContextFactory(request).create()

    def _resolve_json_response_from_context(
        self,
        context: AttributeCallRequestContext,
    ) -> JsonResponse:
        glue_object = glue_class_registry.get_glue_class(
            context.target_glue_policy.namespace
        ).from_attribute_call_resolver_context(context)

        return glue_object.process_attribute_call(context)

    @property
    def _glue_error_context(self) -> str:
        return (
            f"object={self.kwargs.get('object_name')}, "
            f"attribute={self.kwargs.get('attribute_name')}"
        )
