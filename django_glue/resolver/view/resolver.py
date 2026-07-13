import logging
from urllib.parse import urlparse

from django.http import HttpRequest, JsonResponse, HttpResponse, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import reverse, resolve, NoReverseMatch
from django.utils.functional import cached_property

from django_glue.conf import settings
from django_glue.constants import DJANGO_GLUE_PROXIES_REQUEST_ATTR_KEY
from django_glue.resolver.attribute_event.encoders import BoundAttributeDataJSONEncoder
from django_glue.resolver.exceptions import GlueResolverError
from django_glue.resolver.resolver import BaseResolver
from django_glue.resolver.view.request import ViewHttpRequest
from django_glue.resolver.view.schemas import ViewBodySchema


class ViewResolver(BaseResolver):
    def __init__(self, request: HttpRequest) -> None:
        self.request = request
        self.view_body = ViewBodySchema.from_request(request)

    @cached_property
    def glue_view_http_request(self) -> ViewHttpRequest:
        return ViewHttpRequest(
            base_request=self.request,
            method=self.view_body.method,
            url_path=self.view_body.url_path,
            view_payload=self.view_body.view_payload,
        )

    def get_response(self) -> HttpResponse:
        parsed = urlparse(self.view_body.url_path)
        resolve_path = parsed.path

        try:
            resolved = resolve(resolve_path)
        except NoReverseMatch:
            raise GlueResolverError(
                response_error=f'No view found for URL path: {self.view_body.url_path}', response_status=404
            ) from NoReverseMatch

        view_func = resolved.func
        view_kwargs = resolved.kwargs

        try:
            return view_func(self.glue_view_http_request, **view_kwargs)
        except Exception as e:
            logging.exception(e)
            raise GlueResolverError(
                response_error=f'View raised an exception: {e!s}', response_status=500
            ) from Exception

    def resolve(self) -> JsonResponse:
        try:
            for _ in range(settings.DJANGO_GLUE_VIEW_MAX_REDIRECTS):
                response = self.get_response()

                if isinstance(response, HttpResponseRedirect):
                    redirect_url = response.url
                    if redirect_url.startswith('/'):
                        try:
                            resolved_redirect = resolve(redirect_url)
                            self.view_body.url_name = resolved_redirect.view_name
                            self.view_body.url_path = reverse(self.view_body.url_name)
                        except NoReverseMatch:
                            raise GlueResolverError(
                                response_error=f'Could not resolve redirect URL: {redirect_url}',
                                response_status=404,
                            ) from NoReverseMatch
                    else:
                        self.raise_external_redirects_not_supported(redirect_url)
                    continue

                if isinstance(response, TemplateResponse):
                    response.render()

                    return JsonResponse(
                        {
                            'html': response.content.decode('utf-8'),
                            'proxies': getattr(
                                self.glue_view_http_request, DJANGO_GLUE_PROXIES_REQUEST_ATTR_KEY, {}
                            ),
                        },
                        safe=False,
                        encoder=BoundAttributeDataJSONEncoder,
                    )

                if isinstance(response, HttpResponse):
                    return JsonResponse(
                        {
                            'html': response.content.decode('utf-8'),
                            'proxies': getattr(
                                self.glue_view_http_request, DJANGO_GLUE_PROXIES_REQUEST_ATTR_KEY, {}
                            ),
                        }
                    )

                self.raise_unsupported_response_type(response)

            self.raise_to_many_redirects()

        except GlueResolverError as e:
            return JsonResponse({'error': e.response_error}, status=e.response_status)

    def raise_external_redirects_not_supported(self, redirect_url: str) -> None:
        raise GlueResolverError(
            response_error=f'External redirect not supported: {redirect_url}', response_status=400
        )

    def raise_to_many_redirects(self) -> None:
        raise GlueResolverError(
            response_error=f'Too many redirects (max {settings.DJANGO_GLUE_VIEW_MAX_REDIRECTS})',
            response_status=500,
        )

    def raise_unsupported_response_type(self, response: HttpResponse) -> None:
        raise GlueResolverError(
            response_error=f'Unsupported response type: {type(response).__name__}',
            response_status=500,
        )
