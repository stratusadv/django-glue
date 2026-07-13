from __future__ import annotations

import json
from typing import Any
from pydantic import BaseModel, model_validator

from django.http import HttpRequest

from django_glue.bound_attributes.attribute import BoundProxyAttribute
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
            msg = f'Expected multipart/form-data, got {request.content_type}'
            raise ValueError(msg)

        raw_policy = request.POST.get('policy')
        if not raw_policy:
            msg = '"policy" is required'
            raise ValueError(msg)

        policy = ProxyPolicy(**json.loads(raw_policy))

        if not request.resolver_match:
            msg = 'No path parameters'
            raise ValueError(msg)

        if request.resolver_match.kwargs.get('proxy_name') != policy.name:
            msg = 'Proxy name mismatch between URL path and policy'
            raise ValueError(msg)

        current_session_id = request.session.session_key
        if policy.session_id != current_session_id:
            from django_glue.exceptions import GlueInvalidPolicyError  # noqa: PLC0415
            raise GlueInvalidPolicyError(policy.name)

        bound_attribute_name = request.resolver_match.kwargs.get('attribute_name')
        if not bound_attribute_name:
            msg = 'No bound_attribute name sent in URL path'
            raise ValueError(msg)

        bound_attribute_data = policy.bound_attributes.get(bound_attribute_name)
        if not bound_attribute_data:
            msg = f'Bound attribute for event was not included in policy: {bound_attribute_name}'
            raise ValueError(msg)

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

        return {
            'request': request,
            'bound_attribute': bound_attribute,
            'policy': policy,
            'event_kwargs': json.loads(event_kwargs_raw) if event_kwargs_raw else None,
            'proxy_state': json.loads(proxy_state) if proxy_state else None,
        }
