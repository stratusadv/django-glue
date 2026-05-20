from __future__ import annotations

import json
from typing import TYPE_CHECKING

from django.urls import reverse, NoReverseMatch
from pydantic import BaseModel, ConfigDict, Field

from django_glue.resolver.exceptions import GlueResolverError
from django_glue.utils import get_request_body_data

if TYPE_CHECKING:
    from django.http import HttpRequest, JsonResponse


class ViewBodySchema(BaseModel):
    model_config = ConfigDict(extra='allow')

    url_name: str | None = None
    url_path: str | None = None
    method: str = 'POST'
    view_payload: dict = Field(default=dict)

    @classmethod
    def from_request(cls, request: HttpRequest) -> ViewBodySchema:
        body_data = get_request_body_data(request)

        return cls(**body_data)

    def get_url_path(self) -> str | JsonResponse:
        if self.url_name:
            try:
                return reverse(self.url_name)
            except NoReverseMatch:
                raise GlueResolverError(
                    response_error=f'Could not resolve URL name: {self.url_name}', response_status=404
                ) from NoReverseMatch

        elif self.url_path:
            return self.url_path

        else:
            raise GlueResolverError(
                response_error='Missing url_name or url_path in request body', response_status=400
            )
