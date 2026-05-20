from typing import Callable

from django.http import HttpResponse, HttpRequest
from django.urls import resolve, Resolver404

from django_glue import constants
from django_glue.session import GlueSession


class DjangoGlueMiddleware:
    def __init__(self, get_response: Callable) -> None:
        self.get_response = get_response

    @staticmethod
    def _is_glue_view_request(request: HttpRequest) -> bool:
        try:
            resolved = resolve(request.path_info)
        except Resolver404:
            return False
        return resolved.view_name in [
            f'{constants.BASE_URL_NAME}:{constants.ACTION_URL_NAME}',
            f'{constants.BASE_URL_NAME}:{constants.KEEP_LIVE_URL_NAME}',
            f'{constants.BASE_URL_NAME}:{constants.SESSION_DATA_URL_NAME}',
            f'{constants.BASE_URL_NAME}:{constants.GLUE_VIEW_URL_NAME}',
        ]

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if not self._is_glue_view_request(request):
            GlueSession(request).purge_expired_proxies()

        return self.get_response(request)
