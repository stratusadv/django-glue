from __future__ import annotations
from typing import TYPE_CHECKING

import json

from pydantic import BaseModel

from django_glue.utils import get_request_body_data

if TYPE_CHECKING:
    from django.http import HttpRequest


class ActionPayloadSchema(BaseModel):
    context_data: dict
    post_data: dict | None = None
    file_data: dict | None = None

    @classmethod
    def from_request(cls, request: HttpRequest) -> ActionPayloadSchema:
        if request.content_type == 'multipart/form-data':
            post_data = {}

            for key in request.POST:
                values = request.POST.getlist(key)
                # If multiple values, keep as list; otherwise unwrap single value
                post_data[key] = values if len(values) > 1 else values[0]

            context_data = post_data.pop('context_data', None)
            if context_data is None:
                message = 'context_data is required in a Glue action request'
                raise AttributeError(message)

            return cls(
                context_data=json.loads(context_data),
                post_data=post_data,
                file_data=request.FILES.dict(),
            )
        body_data = get_request_body_data(request)

        return cls(**body_data)
