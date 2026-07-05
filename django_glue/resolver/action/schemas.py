from __future__ import annotations
from typing import TYPE_CHECKING, Any

import json

from django.http import JsonResponse
from pydantic import BaseModel, ValidationError, model_validator
from pydantic.dataclasses import dataclass

from django_glue.proxies.contract import GlueProxyContract
from django_glue.maps import SUBJECT_TYPE_TO_PROXY_CLASS
from django.http import HttpRequest

if TYPE_CHECKING:
    from django_glue.proxies.proxy import BaseGlueProxy

@dataclass
class ActionRequest(BaseModel):
    """
    BaseModel for action requests.

    All action requests use multipart/form-data for consistent handling of
    all data types including files.

    Attributes:
        action_name: Name of the action requested.
        action_kwargs: Action-specific keyword arguments (e.g., step number, filter params).
                This is what the user explicitly passes to the
                action from the frontend proxy action method calls.
        contract: Immutable proxy contract defined at the time of proxy registration and used for
            subject reconstruction.
            Signed and verified to prevent tampering.
        state: Proxy-intrinsic runtime state (e.g., form field state, instance ids).
            This data is specific to the proxy type and is sent
            back and forth between action calls. It, together with the contract,
            are used to reconstruct subjects.

    """

    request: HttpRequest
    action_name: str
    contract: GlueProxyContract
    state: dict | None = None
    action_kwargs: dict | None = None

    @model_validator(mode='before')
    def _process_request(self, data: Any) -> dict:
        request = data.get('request', None)
        if not isinstance(request, HttpRequest):
            msg = 'ActionRequest objects must be constructed from HttpRequests'
            raise ValidationError(msg)

        if request.content_type != 'multipart/form-data':
            msg = f'Action requests must use multipart/form-data, got {request.content_type}'

            raise ValidationError(msg)

        raw_proxy_contract = request.POST.get('contract', None)
        if raw_proxy_contract is None:
            msg = '"contract" is required in a Glue action request'
            raise ValidationError(msg)

        contract = GlueProxyContract(**json.loads(raw_proxy_contract))

        if not request.resolver_match:
            msg = 'Incoming HttpRequest has no path parameters'
            raise ValidationError(msg)

        if request.resolver_match.kwargs.get('proxy_name') != contract.name:
            msg = (
                'Incoming HttpRequest tried to request action for a '
                'proxy other than the one in the contract it sent.'
            )
            raise ValidationError(msg)

        action_name = request.resolver_match.kwargs.get('action')
        if not action_name or action_name not in contract.actions:
            msg = (
                'Incoming HttpRequest requested an'
                ' invalid action the proxy contract it contained.'
            )
            raise ValidationError(msg)

        raw_proxy_state = request.POST.get('raw_proxy_state')
        action_kwargs_raw = request.POST.get('action_kwargs')

        return {
            'action_name': action_name,
            'request': request,
            'contract': GlueProxyContract(**json.loads(raw_proxy_contract)),
            'action_kwargs': json.loads(action_kwargs_raw) if action_kwargs_raw else None,
            'state': json.loads(raw_proxy_state) if raw_proxy_state else None,
        }

    @property
    def action_target_class(self) -> type:
        return self.contract.actions[self.action_name].target_class

    def process(self) -> JsonResponse:
        proxy_class: BaseGlueProxy = SUBJECT_TYPE_TO_PROXY_CLASS[
            self.contract.namespace
        ]

        return proxy_class.process_action_request(self).to_response()


