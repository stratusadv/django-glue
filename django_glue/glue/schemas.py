from __future__ import annotations

import json
from json import JSONDecodeError
from typing import Any

from django.http import HttpRequest
from pydantic import BaseModel, Field, model_validator

from django_glue.glue.policy import GluePolicy
from django_glue.exceptions import GlueInvalidPolicyError, GlueInvalidSessionError, GlueRequestError


class GlueAttributeRequest(BaseModel):
    """Parsed adapter attribute request."""

    model_config = {'arbitrary_types_allowed': True}

    request: HttpRequest
    policy: GluePolicy
    state: Any = None
    attribute: str
    kwargs: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode='before')
    @classmethod
    def validate_http_request(cls, request: HttpRequest, *_) -> Any:
        if request.content_type != 'multipart/form-data':
            raise GlueRequestError(
                code='invalid_content_type',
                message=f'Expected multipart/form-data, got {request.content_type}',
                details={'content_type': request.content_type},
            )

        policy = cls._load_json_field(request, 'policy', required=True)
        state = cls._load_json_field(request, 'state', required=False)
        kwargs = cls._load_json_field(request, 'kwargs', required=False) or {}
        if not isinstance(kwargs, dict):
            raise GlueRequestError(
                code='invalid_kwargs',
                message='"kwargs" must be a JSON object.',
                details={'type': type(kwargs).__name__},
            )

        attribute = request.POST.get('attribute')
        if not attribute:
            raise GlueRequestError(
                code='missing_attribute',
                message='"attribute" is required.',
            )

        parsed_policy = GluePolicy.model_validate(policy)

        if not request.resolver_match:
            raise GlueRequestError(
                code='missing_path_parameters',
                message='No path parameters were available for the Glue attribute request.',
            )

        path_name = request.resolver_match.kwargs.get('object_name')
        if path_name != parsed_policy.name:
            raise GlueRequestError(
                code='policy_name_mismatch',
                message='Object name mismatch between URL path and policy.',
                details={'path_name': path_name, 'policy_name': parsed_policy.name},
            )

        current_session_id = request.session.session_key
        if parsed_policy.session_id != current_session_id:
            raise GlueInvalidSessionError(parsed_policy.name)

        return {
            'request': request,
            'policy': parsed_policy,
            'state': state,
            'attribute': attribute,
            'kwargs': kwargs,
        }

    @staticmethod
    def _load_json_field(request: HttpRequest, field_name: str, *, required: bool) -> Any:
        raw_value = request.POST.get(field_name)
        if not raw_value:
            if required:
                raise GlueRequestError(
                    code=f'missing_{field_name}',
                    message=f'"{field_name}" is required.',
                )
            return None

        try:
            return json.loads(raw_value)
        except JSONDecodeError as e:
            raise GlueRequestError(
                code=f'invalid_{field_name}_json',
                message=f'{field_name} must be valid JSON.',
                details={'error': str(e)},
            ) from e
