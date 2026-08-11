"""Validated context for resolving a client-initiated attribute call."""

from __future__ import annotations

import json
from json import JSONDecodeError
from typing import Any
from pydantic import BaseModel, Field, ValidationError

from django.http import HttpRequest  # noqa: TC002 - need for base model annotation
from django.conf import settings

from django_glue.exceptions import (
    GlueInvalidSessionError,
    GlueInvalidUserError,
    GlueRequestError,
    GlueRequestErrorCode,
)
from django_glue.glue.policy import GluePolicy


class AttributeCallRequestContext(BaseModel):
    """
    Validated input context for resolving a client-initiated attribute call.

    This object contains the validated components needed to resolve an attribute
    call against a Glue object. All fields represent client-provided data that
    has been validated for structure but not yet for authorization or business logic.

    Use AttributeCallRequestParser to construct this from an HttpRequest.
    """

    model_config = {'arbitrary_types_allowed': True}

    request: HttpRequest
    target_glue_policy: GluePolicy
    target_glue_client_state: Any = None
    target_attribute_name: str
    target_attribute_call_kwargs: dict[str, Any] = Field(default_factory=dict)


class AttributeCallContextFactory:
    """
    Factory that parses and validates an HTTP request into an AttributeCallContext.

    Usage:
        context = AttributeCallContextFactory(request).create()
    """

    def __init__(self, request: HttpRequest) -> None:
        self.request = request

        # Accumulated during parsing
        self._policy_dict: dict[str, Any] | None = None
        self._validated_policy: GluePolicy | None = None
        self._state: Any = None
        self._kwargs: dict[str, Any] = {}
        self._attribute: str | None = None

    def create(self) -> AttributeCallRequestContext:
        """
        Execute all validation steps and return the validated context.

        Raises GlueRequestError for malformed requests,
        GlueInvalidSessionError/GlueInvalidUserError for auth mismatches.
        """
        self._validate_content_type()
        self._parse_json_fields()
        self._parse_attribute()
        self._validate_policy()
        self._validate_path_params_match_policy()
        self._validate_session_and_user()

        try:
            return AttributeCallRequestContext(
                request=self.request,
                target_glue_policy=self._validated_policy,  # type: ignore[arg-type]
                target_glue_client_state=self._state,
                target_attribute_name=self._attribute,  # type: ignore[arg-type]
                target_attribute_call_kwargs=self._kwargs,
            )
        except ValidationError as e:
            message = f'{e}' if settings.DEBUG else 'Malformed Glue Attribute Request'
            raise GlueRequestError(
                code=GlueRequestErrorCode.MALFORMED_REQUEST,
                message=message,
                details={'errors': e.errors(include_input=False)} if settings.DEBUG else {},
            ) from e

    def _validate_content_type(self) -> None:
        if self.request.content_type != 'multipart/form-data':
            raise GlueRequestError(
                code=GlueRequestErrorCode.INVALID_CONTENT_TYPE,
                message=f'Expected multipart/form-data, got {self.request.content_type}',
                details={'content_type': self.request.content_type},
            )

    def _parse_json_fields(self) -> None:
        self._policy_dict = self._load_json_field('policy', required=True)
        self._state = self._load_json_field('state', required=False)

        kwargs = self._load_json_field('kwargs', required=False) or {}
        if not isinstance(kwargs, dict):
            raise GlueRequestError(
                code=GlueRequestErrorCode.INVALID_KWARGS,
                message='"kwargs" must be a JSON object.',
                details={'type': type(kwargs).__name__},
            )
        self._kwargs = kwargs

    def _parse_attribute(self) -> None:
        attribute = self.request.POST.get('attribute')
        if not attribute:
            raise GlueRequestError(
                code=GlueRequestErrorCode.MISSING_FIELD,
                message='"attribute" is required.',
                details={'field': 'attribute'},
            )
        self._attribute = attribute

    def _validate_policy(self) -> None:
        self._validated_policy = GluePolicy.model_validate(self._policy_dict)

    def _validate_path_params_match_policy(self) -> None:
        if not self.request.resolver_match:
            raise GlueRequestError(
                code=GlueRequestErrorCode.MISSING_PATH_PARAMETERS,
                message='No path parameters were available for the Glue attribute request.',
            )

        path_object_name = self.request.resolver_match.kwargs.get('object_name')
        if path_object_name != self._validated_policy.name:  # type: ignore[union-attr]
            raise GlueRequestError(
                code=GlueRequestErrorCode.OBJECT_NAME_MISMATCH,
                message='Object name mismatch between URL path and policy.',
                details={
                    'path_name': path_object_name,
                    'policy_name': self._validated_policy.name,  # type: ignore[union-attr]
                },
            )

        path_attribute_name = self.request.resolver_match.kwargs.get('attribute_name')
        if path_attribute_name != self._attribute:
            raise GlueRequestError(
                code=GlueRequestErrorCode.ATTRIBUTE_NAME_MISMATCH,
                message='Attribute name mismatch between URL path and request body.',
                details={'path_name': path_attribute_name, 'body_name': self._attribute},
            )

    def _validate_session_and_user(self) -> None:
        policy = self._validated_policy
        assert policy is not None  # Guaranteed by _validate_policy

        current_session_id = self.request.session.session_key
        if policy.session_id != current_session_id:
            raise GlueInvalidSessionError(
                policy.name,
                policy_session_id=policy.session_id,
                current_session_id=current_session_id,
            )

        current_user_id = getattr(getattr(self.request, 'user', None), 'id', None)
        if policy.request_user_id != current_user_id:
            raise GlueInvalidUserError(
                policy.name,
                policy_user_id=policy.request_user_id,
                current_user_id=current_user_id,
            )

    def _load_json_field(self, field_name: str, *, required: bool) -> Any:
        raw_value = self.request.POST.get(field_name)
        if not raw_value:
            if required:
                raise GlueRequestError(
                    code=GlueRequestErrorCode.MISSING_FIELD,
                    message=f'"{field_name}" is required.',
                    details={'field': field_name},
                )
            return None

        try:
            return json.loads(raw_value)
        except JSONDecodeError as e:
            raise GlueRequestError(
                code=GlueRequestErrorCode.INVALID_JSON,
                message=f'{field_name} must be valid JSON.',
                details={'field': field_name, 'error': str(e)},
            ) from e


AttributeCallRequestContext.model_rebuild()
