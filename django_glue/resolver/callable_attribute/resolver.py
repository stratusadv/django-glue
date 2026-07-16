from __future__ import annotations

from typing import TYPE_CHECKING

from django.http import JsonResponse

from django_glue.encoders import GlueResponseJSONEncoder
from django_glue.glue.registry import glue_object_resolver_registry
from django_glue.exceptions import GlueAccessError, GlueMissingAttributeError, GlueRequestError
from django_glue.response import GlueResponse

if TYPE_CHECKING:
    from django_glue.glue.attributes import BaseGlueAttribute
    from django_glue.glue.base import BaseGlue
    from django_glue.glue.policy import GluePolicy
    from django_glue.glue.schemas import GlueAttributeRequest


class GlueCallableAttributeResolver:
    """Resolve an adapter-backed Glue attribute request."""

    def __init__(self, attribute_request: GlueAttributeRequest) -> None:
        self.attribute_request = attribute_request

    @property
    def policy(self) -> GluePolicy:
        return self.attribute_request.policy

    @property
    def attribute_name(self) -> str:
        return self.attribute_request.attribute

    def _validate_policy_allows_attribute(self) -> None:
        if self.attribute_name not in self.policy.attributes:
            raise GlueMissingAttributeError(self.attribute_name, self.policy.name)

    def _get_attribute(self, glue_object) -> BaseGlueAttribute:
        attribute = glue_object.attributes.get(self.attribute_name)
        if attribute is None:
            raise GlueMissingAttributeError(self.attribute_name, self.policy.name)
        return attribute

    def _validate_callable_attribute(self, attribute: BaseGlueAttribute) -> None:
        if not self.policy.access.has_access(attribute.required_access):
            raise GlueAccessError(
                attribute=self.attribute_name,
                required_access=attribute.required_access.value,
                current_access=self.policy.access.value,
            )

        if not attribute.is_callable:
            raise GlueRequestError(
                code='attribute_not_callable',
                message=f"Attribute '{self.attribute_name}' is not callable.",
                details={'attribute': self.attribute_name},
                status=422,
            )

    def resolve(self) -> JsonResponse:
        self._validate_policy_allows_attribute()

        glue_object = glue_object_resolver_registry.get_object_for_policy(
            self.policy,
            self.attribute_request.request,
        )
        attribute = self._get_attribute(glue_object)
        self._validate_callable_attribute(attribute)
        result = glue_object.call_attribute(
            state=self.attribute_request.state,
            attribute_name=self.attribute_name,
            kwargs=self.attribute_request.kwargs,
            policy=self.policy,
            request=self.attribute_request.request,
        )

        self.policy.refresh_signature()
        response = result if isinstance(result, GlueResponse) else GlueResponse(result=result)
        return self._to_json_response(response, glue_object)

    def _to_json_response(self, response: GlueResponse, glue_object: BaseGlue) -> JsonResponse:
        return JsonResponse(
            data={
                'result': response.result if response.result is not None else {},
                'state': glue_object.state,
                'policy': self.policy.model_dump(),
                'metadata': glue_object.metadata.to_payload(),
                'messages': [message.to_dict() for message in response.messages],
            },
            status=response.status,
            safe=True,
            encoder=GlueResponseJSONEncoder,
        )
