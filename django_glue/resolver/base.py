from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from django.views import View
from pydantic import BaseModel

from django_glue.exceptions import GlueError
from django_glue.response import GlueResponse

if TYPE_CHECKING:
    from django.http import HttpRequest, JsonResponse

logger = logging.getLogger('django.request')
GlueRequestContext = TypeVar('GlueRequestContext', bound=BaseModel)


class GlueResolver(View, Generic[GlueRequestContext]):
    http_method_names = ['post']

    def post(
        self,
        request: HttpRequest,
        *_args: Any,
        **_kwargs: Any,
    ) -> JsonResponse:
        try:
            context = self._create_context_from_request(request)
        except GlueError as error:
            return self._error_response(
                error=error,
                message=f'Context creation for {self.__class__.__name__} failed',
            )

        try:
            return self._resolve_json_response_from_context(context)
        except GlueError as error:
            message = (
                'An error occurred when trying to resolve a request using '
                f'{self.__class__.__name__}'
            )
            return self._error_response(
                error=error,
                message=message,
            )

    def _create_context_from_request(self, request: HttpRequest) -> GlueRequestContext:
        raise NotImplementedError

    def _resolve_json_response_from_context(self, context: GlueRequestContext) -> JsonResponse:
        raise NotImplementedError

    def _error_response(self, message: str, error: GlueError) -> JsonResponse:
        if error.status >= 500:
            logger.exception('%s: %s', message, self._glue_error_context)

        return GlueResponse.from_error(error).to_json_response()

    @property
    def _glue_error_context(self) -> str:
        return f'path={self.request.path}'
