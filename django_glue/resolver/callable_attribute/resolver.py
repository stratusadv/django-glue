from __future__ import annotations

from typing import TYPE_CHECKING

from django.http import JsonResponse

from django_glue.encoders import GlueResponseJSONEncoder
from django_glue.glue.attributes.callable import CallableAttribute
from django_glue.glue.registry import glue_object_resolver_registry
from django_glue.exceptions import GlueAccessError, GlueMissingAttributeError, GlueRequestError
from django_glue.response import GlueResponse

if TYPE_CHECKING:
    from django_glue.glue.attributes import BaseGlueAttribute
    from django_glue.glue.base import BaseGlue
    from django_glue.glue.policy import GluePolicy
    from django_glue.glue.schemas import AttributeCallResolverContext


class AttributeCallResolver:
    """Resolve an adapter-backed Glue attribute request."""

    def __init__(self, context: AttributeCallResolverContext) -> None:
        self.context = context

    def _validate_policy_allows_attribute(self) -> None:
        if self.context.target_attribute_name not in self.context.target_glue_policy.attributes:
            raise GlueMissingAttributeError(
                self.context.target_attribute_name,
                self.context.target_glue_policy.name
            )

    def _get_attribute(self, glue_object: BaseGlue) -> BaseGlueAttribute:
        attribute = glue_object.attributes.get(self.context.target_attribute_name)
        if attribute is None:
            raise GlueMissingAttributeError(
                self.context.target_attribute_name,
                self.context.target_glue_policy.name
            )
        return attribute

    def _validate_callable_attribute(self, attribute: BaseGlueAttribute) -> None:
        if not self.context.target_glue_policy.access.has_access(attribute.required_access):
            raise GlueAccessError(
                attribute=self.context.target_attribute_name,
                required_access=attribute.required_access.value,
                current_access=self.context.target_glue_policy.access.value,
            )

        if not isinstance(attribute, CallableAttribute):
            raise GlueRequestError(
                code='attribute_not_callable',
                message=f"Attribute '{self.context.target_attribute_name}' is not callable.",
                details={'attribute': self.context.target_attribute_name},
                status=422,
            )

    def resolve(self) -> JsonResponse:
        self._validate_policy_allows_attribute()

        glue_object = glue_object_resolver_registry.get_object_for_policy(
            self.context.target_glue_policy,
            self.context.request,
        )
        attribute = self._get_attribute(glue_object)
        self._validate_callable_attribute(attribute)
        result = glue_object.call_attribute(
            state=self.context.target_glue_client_state,
            attribute_name=self.context.target_attribute_name,
            kwargs=self.context.target_attribute_call_kwargs,
            policy=self.context.target_glue_policy,
            request=self.context.request,
        )

        self.context.target_glue_policy.refresh_signature()
        response = result if isinstance(result, GlueResponse) else GlueResponse(result=result)
        return self._to_json_response(response, glue_object)

    def _to_json_response(self, response: GlueResponse, glue_object: BaseGlue) -> JsonResponse:
        return JsonResponse(
            data={
                'result': response.result if response.result is not None else {},
                'state': glue_object.state,
                'policy': self.context.target_glue_policy.model_dump(),
                'metadata': glue_object.metadata.to_payload(),
                'messages': [message.to_dict() for message in response.messages],
            },
            status=response.status,
            safe=True,
            encoder=GlueResponseJSONEncoder,
        )
