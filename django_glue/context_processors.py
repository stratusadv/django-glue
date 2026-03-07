from __future__ import annotations
from typing import TYPE_CHECKING

from django.urls import reverse

from django_glue import constants
from django_glue.conf import settings
from django_glue.session import GlueSession

if TYPE_CHECKING:
    from django.core.handlers.wsgi import WSGIRequest

def django_glue(request: WSGIRequest) -> dict:
    data = {
        'DJANGO_GLUE_URLS': {
            'action': f'/{constants.BASE_URL_NAME}/{constants.ACTION_URL_NAME}',
        },
        constants.DJANGO_GLUE_VERSION: constants.__VERSION__,
        constants.DJANGO_GLUE_URL_APP_NAME: constants.BASE_URL_NAME,
        constants.DJANGO_GLUE_KEEP_LIVE_INTERVAL_TIME_MILLISECONDS: (settings.DJANGO_GLUE_KEEP_LIVE_INTERVAL_TIME_SECONDS / 2.2) * 1000,
        constants.DJANGO_GLUE_SESSION_PROXY_REGISTRY: GlueSession(request).proxy_registry,
        constants.DJANGO_GLUE_PROXIES_CONTEXT_DATA: {},
    }

    if hasattr(request, '__glue_context_data__'):
        data[constants.DJANGO_GLUE_PROXIES_CONTEXT_DATA] = request.__glue_context_data__

    return data