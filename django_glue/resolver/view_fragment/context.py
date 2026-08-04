from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.urls import NoReverseMatch, reverse
from pydantic import BaseModel, ConfigDict, Field

from django_glue.exceptions import GlueRequestError, GlueRequestErrorCode
from django_glue.utils import get_request_body_data

if TYPE_CHECKING:
    from django.http import HttpRequest


class ViewFragmentRequestContext(BaseModel):
    model_config = ConfigDict(extra='allow')

    url_name: str | None = None
    url_path: str | None = None
    method: str = 'POST'
    view_payload: dict = Field(default_factory=dict)

    def model_post_init(self, _context: Any, /) -> None:
        if self.url_name:
            try:
                self.url_path = reverse(self.url_name)
            except NoReverseMatch as error:
                raise GlueRequestError(
                    code=GlueRequestErrorCode.VIEW_URL_NAME_NOT_FOUND,
                    message=f'Could not resolve URL name: {self.url_name}',
                    status=404,
                ) from error

        elif self.url_path is None:
            raise GlueRequestError(
                code=GlueRequestErrorCode.MISSING_VIEW_TARGET,
                message='Missing url_name or url_path in request body',
            )

    @classmethod
    def from_request(cls, request: HttpRequest) -> ViewFragmentRequestContext:
        body_data = get_request_body_data(request)

        return cls(**body_data)
