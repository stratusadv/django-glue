from django.urls import resolve

from django_glue import constants
from django_glue.session import GlueSession


class DjangoGlueMiddleware(object):
    def __init__(self, get_response):
        self.get_response = get_response

    @staticmethod
    def _is_glue_view_request(request):
        return resolve(request.path_info).view_name in [
            f'{constants.BASE_URL_NAME}:{constants.ACTION_URL_NAME}',
            f'{constants.BASE_URL_NAME}:{constants.KEEP_LIVE_URL_NAME}'
        ]

    def __call__(self, request):
        if not self._is_glue_view_request(request):
            GlueSession(request).purge_expired_proxies()

        return self.get_response(request)
