from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from django.conf import settings
from django.core.checks import Error
from django.http import JsonResponse
from django.utils.cache import patch_vary_headers

from django_glue.constants import GLUE_VIEW_MEDIA_TYPE
from django_glue.encoders import GlueResponseJSONEncoder
from django_glue.response import render_html_payload

if TYPE_CHECKING:
    from django.http import HttpRequest, HttpResponse


GLUE_VIEW_MIDDLEWARE_PATH = 'django_glue.middleware.GlueViewMiddleware'


class GlueViewMiddleware:
    """Package a rendered HTML response as the `Glue.view` envelope when the
    request negotiates it (state-model.md §6, ADR 003).

    The target view runs through the complete, ordinary middleware chain; this
    only changes the representation, so it must be the last entry in
    ``MIDDLEWARE``.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        if response.streaming or not response.get('Content-Type', '').startswith('text/html'):
            return response

        patch_vary_headers(response, ('Accept',))
        if GLUE_VIEW_MEDIA_TYPE not in request.headers.get('Accept', ''):
            return response
        if not 200 <= response.status_code < 300:
            return response

        envelope = JsonResponse(
            {'is_glue_template_response': True, **render_html_payload(response, request)},
            encoder=GlueResponseJSONEncoder,
        )
        patch_vary_headers(envelope, ('Accept',))
        return envelope


def check_glue_view_middleware(app_configs: Any = None, **kwargs: Any) -> list[Error]:
    _ = app_configs, kwargs
    middleware = list(getattr(settings, 'MIDDLEWARE', None) or ())
    if middleware and middleware[-1] == GLUE_VIEW_MIDDLEWARE_PATH:
        return []
    return [Error(
        f'{GLUE_VIEW_MIDDLEWARE_PATH} must be the last entry in MIDDLEWARE.',
        hint=(
            'Glue.view negotiates the final response; every other middleware must '
            'run before it so none is bypassed.'
        ),
        id='django_glue.E002',
    )]
