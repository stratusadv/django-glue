from __future__ import annotations

import logging
from typing import TYPE_CHECKING, NoReturn
from urllib.parse import urlparse

from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.template.response import TemplateResponse
from django.urls import NoReverseMatch, resolve, reverse

from django_glue.conf import settings
from django_glue.encoders import GlueResponseJSONEncoder
from django_glue.exceptions import GlueRequestError, GlueRequestErrorCode
from django_glue.glue.context import GlueContextManager
from django_glue.resolver.base import GlueResolver
from django_glue.resolver.view_fragment.context import ViewFragmentRequestContext
from django_glue.resolver.view_fragment.request import ViewFragmentHttpRequest

if TYPE_CHECKING:
    from django.http import HttpRequest

logger = logging.getLogger('django.request')


class GlueViewFragmentResolver(GlueResolver[ViewFragmentRequestContext]):
    def _create_context_from_request(self, request: HttpRequest) -> ViewFragmentRequestContext:
        return ViewFragmentRequestContext.from_request(request)

    def _resolve_json_response_from_context(
        self,
        context: ViewFragmentRequestContext,
    ) -> JsonResponse:
        for _ in range(settings.DJANGO_GLUE_VIEW_MAX_REDIRECTS):
            response = self._call_resolved_view(context)

            if isinstance(response, HttpResponseRedirect):
                context = self._redirected_context(context, response)
                continue

            return self._render_response(response)

        return self._raise_too_many_redirects()

    def _serialized_new_glue_manifests(self) -> list[dict]:
        return [manifest.model_dump() for manifest in GlueContextManager(self.request).manifests]

    def _build_glue_view_http_request(
        self,
        context: ViewFragmentRequestContext,
    ) -> ViewFragmentHttpRequest:
        return ViewFragmentHttpRequest(
            base_request=self.request,
            method=context.method,
            url_path=context.url_path,
            view_payload=context.view_payload,
        )

    def _call_resolved_view(self, context: ViewFragmentRequestContext) -> HttpResponse:
        parsed = urlparse(context.url_path)
        resolve_path = parsed.path

        try:
            resolved = resolve(resolve_path)
        except NoReverseMatch as error:
            raise GlueRequestError(
                code=GlueRequestErrorCode.VIEW_URL_PATH_NOT_FOUND,
                message=f'No view found for URL path: {context.url_path}',
                status=404,
            ) from error

        try:
            return resolved.func(
                self._build_glue_view_http_request(context),
                **resolved.kwargs,
            )
        except Exception as e:
            logger.exception('Resolved Glue view raised an exception')
            raise GlueRequestError(
                code=GlueRequestErrorCode.VIEW_CALL_FAILED,
                message=f'View raised an exception: {e!s}',
                status=500,
            ) from e

    def _redirected_context(
        self,
        context: ViewFragmentRequestContext,
        response: HttpResponseRedirect,
    ) -> ViewFragmentRequestContext:
        redirect_url = response.url
        if not redirect_url.startswith('/'):
            self._raise_external_redirects_not_supported(redirect_url)

        try:
            resolved_redirect = resolve(redirect_url)
            return context.model_copy(
                update={
                    'url_name': resolved_redirect.view_name,
                    'url_path': reverse(resolved_redirect.view_name),
                }
            )
        except NoReverseMatch as error:
            raise GlueRequestError(
                code=GlueRequestErrorCode.VIEW_REDIRECT_URL_NOT_FOUND,
                message=f'Could not resolve redirect URL: {redirect_url}',
                status=404,
            ) from error

    def _render_response(self, response: HttpResponse) -> JsonResponse:
        if isinstance(response, TemplateResponse):
            response.render()

        if isinstance(response, HttpResponse):
            return JsonResponse(
                {
                    'html': response.content.decode('utf-8'),
                    'manifest_list': self._serialized_new_glue_manifests(),
                },
                safe=False,
                encoder=GlueResponseJSONEncoder,
            )

        return self._raise_unsupported_response_type(response)

    def _raise_external_redirects_not_supported(self, redirect_url: str) -> NoReturn:
        raise GlueRequestError(
            code=GlueRequestErrorCode.EXTERNAL_VIEW_REDIRECT_NOT_SUPPORTED,
            message=f'External redirect not supported: {redirect_url}',
        )

    def _raise_too_many_redirects(self) -> NoReturn:
        raise GlueRequestError(
            code=GlueRequestErrorCode.TOO_MANY_VIEW_REDIRECTS,
            message=f'Too many redirects (max {settings.DJANGO_GLUE_VIEW_MAX_REDIRECTS})',
            status=500,
        )

    def _raise_unsupported_response_type(self, response: HttpResponse) -> NoReturn:
        raise GlueRequestError(
            code=GlueRequestErrorCode.UNSUPPORTED_VIEW_RESPONSE_TYPE,
            message=f'Unsupported response type: {type(response).__name__}',
            status=500,
        )

    @property
    def _glue_error_context(self) -> str:
        return f'path={self.request.path}'
