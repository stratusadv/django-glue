from __future__ import annotations
from typing import TYPE_CHECKING

import json

from pydantic import BaseModel

if TYPE_CHECKING:
    from django.http import HttpRequest


class ActionPayloadSchema(BaseModel):
    """
    Schema for action request payloads.

    All action requests use multipart/form-data for consistent handling of
    all data types including files.

    Attributes:
        context_data: Immutable proxy metadata used for server-side reconstruction.
                     Signed and verified to prevent tampering.
        proxy_data: Proxy-intrinsic runtime state (e.g., form_values, instance_pk).
                   This data is specific to the proxy type and persists across calls.
        user_data: Action-specific user data (e.g., step number, filter params).
                  This is what the user explicitly passes to the action.
        file_data: File uploads from the request.
    """
    context_data: dict
    proxy_data: dict | None = None
    user_data: dict | None = None
    file_data: dict | None = None

    @classmethod
    def from_request(cls, request: HttpRequest) -> ActionPayloadSchema:
        """
        Parse an action request. All requests are expected to be multipart/form-data.

        The request POST data contains JSON-serialized strings for:
        - context_data: Required. Proxy metadata for reconstruction.
        - proxy_data: Optional. Proxy-intrinsic state (e.g., form_values).
        - user_data: Optional. Action-specific user data.

        Files are extracted from request.FILES.
        """
        if request.content_type != 'multipart/form-data':
            raise ValueError(
                f'Action requests must use multipart/form-data, got {request.content_type}'
            )

        context_data_raw = request.POST.get('context_data')
        if context_data_raw is None:
            raise AttributeError('context_data is required in a Glue action request')

        proxy_data_raw = request.POST.get('proxy_data')
        user_data_raw = request.POST.get('user_data')

        return cls(
            context_data=json.loads(context_data_raw),
            proxy_data=json.loads(proxy_data_raw) if proxy_data_raw else None,
            user_data=json.loads(user_data_raw) if user_data_raw else None,
            file_data=request.FILES.dict() if request.FILES else None,
        )
