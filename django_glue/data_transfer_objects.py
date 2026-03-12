from __future__ import annotations

import json

from django.http import HttpRequest
from pydantic import BaseModel

from django_glue.utils import get_request_body_data


class GlueActionRequestFormData:
    def __init__(self, request: HttpRequest):
        post_data = request.POST.dict()

        self.context_data = post_data.pop("context_data", None)
        if self.context_data is None:
            raise AttributeError("context_data is required in a Glue action request")

        self.post_data = request.POST.dict()
        self.file_data = request.FILES.dict()


class GlueActionRequestData(BaseModel):
    context_data: dict
    post_data: dict | None = None
    file_data: dict | None = None

    @classmethod
    def from_request(cls, request: HttpRequest) -> GlueActionRequestData:
        if request.content_type == "multipart/form-data":
            post_data = request.POST.dict()

            context_data = post_data.pop("context_data", None)
            if context_data is None:
                raise AttributeError("context_data is required in a Glue action request")

            return cls(
                context_data=json.loads(context_data),
                post_data=post_data,
                file_data=request.FILES.dict(),
            )
        else:
            body_data = get_request_body_data(request)
            return cls(**body_data)

class GlueActionResponseData(BaseModel):
    data: dict
    success: bool
    message: str