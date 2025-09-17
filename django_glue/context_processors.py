from __future__ import annotations
import json
from typing import TYPE_CHECKING

from django.core.serializers.json import DjangoJSONEncoder

from django_glue import constants
from django_glue.conf import settings
from django_glue.session import Session

if TYPE_CHECKING:
    from django.core.handlers.wsgi import WSGIRequest

def django_glue(request: WSGIRequest) -> dict:
    return {
        constants.VERSION_CONTEXT_NAME: constants.__VERSION__,
        constants.KEEP_LIVE_INTERVAL_TIME_MILLISECONDS_CONTEXT_NAME: (settings.DJANGO_GLUE_KEEP_LIVE_EXPIRE_TIME_SECONDS / 2.2) * 1000,
        constants.SESSION_DATA_CONTEXT_NAME: json.dumps(Session(request).session, cls=DjangoJSONEncoder),
    }

def toolbar(request: WSGIRequest) -> dict:
    return {
        f'TOOLBAR_SESSION_DATA': Session(request).session
    }