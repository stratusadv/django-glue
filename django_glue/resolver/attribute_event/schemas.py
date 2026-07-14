from __future__ import annotations

import json
from json import JSONDecodeError
from typing import Any
from pydantic import BaseModel, model_validator

from django.http import HttpRequest

from django_glue.bound_attributes.attribute import BoundProxyAttribute
from django_glue.exceptions import GlueMissingAttributeError, GlueRequestError
from django_glue.proxies.policy import ProxyPolicy


class BoundProxyAttributeEvent(BaseModel):
    """An event emitted by a bound attribute between frontend and backend proxies."""

    model_config = {'arbitrary_types_allowed': True}

    request: HttpRequest
    bound_attribute: BoundProxyAttribute
    policy: ProxyPolicy
    proxy_state: dict | None = None
    event_kwargs: dict | None = None

    @model_validator(mode='before')
    @classmethod
    def validate_http_request(cls, request: HttpRequest, *_) -> Any:
        if request.content_type != 'multipart/form-data':
            raise GlueRequestError(
                code='invalid_content_type',
                message=f'Expected multipart/form-data, got {request.content_type}',
                details={'content_type': request.content_type},
            )

        raw_policy = request.POST.get('policy')
        if not raw_policy:
            raise GlueRequestError(
                code='missing_policy',
                message='"policy" is required',
            )

        try:
            policy_data = json.loads(raw_policy)
        except JSONDecodeError as e:
            raise GlueRequestError(
                code='invalid_policy_json',
                message='Policy must be valid JSON.',
                details={'error': str(e)},
            ) from e

        policy = ProxyPolicy(**policy_data)

        if not request.resolver_match:
            raise GlueRequestError(
                code='missing_path_parameters',
                message='No path parameters were available for the bound attribute event.',
            )

        if request.resolver_match.kwargs.get('proxy_name') != policy.name:
            raise GlueRequestError(
                code='proxy_name_mismatch',
                message='Proxy name mismatch between URL path and policy.',
                details={
                    'path_proxy': request.resolver_match.kwargs.get('proxy_name'),
                    'policy_proxy': policy.name,
                },
            )

        current_session_id = request.session.session_key
        if policy.session_id != current_session_id:
            from django_glue.exceptions import GlueInvalidPolicyError  # noqa: PLC0415
            raise GlueInvalidPolicyError(policy.name)

        bound_attribute_name = request.resolver_match.kwargs.get('attribute_name')
        if not bound_attribute_name:
            raise GlueRequestError(
                code='missing_attribute_name',
                message='No bound attribute name was sent in the URL path.',
                details={'proxy': policy.name},
            )

        bound_attribute_data = policy.bound_attributes.get(bound_attribute_name)
        if not bound_attribute_data:
            raise GlueMissingAttributeError(
                attribute=bound_attribute_name,
                proxy_name=policy.name,
                reason='Attribute was not included in the proxy policy.',
            )

        bound_attribute = BoundProxyAttribute.model_validate(bound_attribute_data)

        event_kwargs_raw = request.POST.get('event_kwargs')
        proxy_state = request.POST.get('state')

        if not policy.access.has_access(bound_attribute.required_access):
            from django_glue.exceptions import GlueAccessError  # noqa: PLC0415
            raise GlueAccessError(
                attribute=bound_attribute.name,
                required_access=bound_attribute.required_access.value,
                current_access=policy.access.value,
            )

        policy.refresh_signature()

        try:
            event_kwargs = json.loads(event_kwargs_raw) if event_kwargs_raw else None
        except JSONDecodeError as e:
            raise GlueRequestError(
                code='invalid_event_kwargs_json',
                message='Event kwargs must be valid JSON.',
                details={'error': str(e)},
            ) from e

        try:
            proxy_state_data = json.loads(proxy_state) if proxy_state else None
        except JSONDecodeError as e:
            raise GlueRequestError(
                code='invalid_state_json',
                message='Proxy state must be valid JSON.',
                details={'error': str(e)},
            ) from e

        return {
            'request': request,
            'bound_attribute': bound_attribute,
            'policy': policy,
            'event_kwargs': event_kwargs,
            'proxy_state': proxy_state_data,
        }
