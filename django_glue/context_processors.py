import json

from django.core.serializers.json import DjangoJSONEncoder

from django_glue.conf import settings
from django_glue import constants
from django_glue.session import Session


def django_glue(request):
    return {
        constants.VERSION_CONTEXT_NAME: constants.__VERSION__,
        constants.KEEP_LIVE_INTERVAL_TIME_MILLISECONDS_CONTEXT_NAME: (settings.DJANGO_GLUE_KEEP_LIVE_EXPIRE_TIME_SECONDS / 2.2) * 1000,
        constants.SESSION_DATA_CONTEXT_NAME: json.dumps(Session(request).session, cls=DjangoJSONEncoder),
    }
