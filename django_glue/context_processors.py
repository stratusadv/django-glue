import json

from django.core.serializers.json import DjangoJSONEncoder

from django_glue.conf import settings
from django_glue import __version__
from django_glue.session import Session


def django_glue(request):
    return {
        'DJANGO_GLUE_VERSION': __version__,
        'DJANGO_GLUE_KEEP_LIVE_INTERVAL_TIME_MILLISECONDS': (settings.DJANGO_GLUE_KEEP_LIVE_EXPIRE_TIME_SECONDS / 2.2) * 1000,
        'DJANGO_GLUE_SESSION_DATA': json.dumps(Session(request).session, cls=DjangoJSONEncoder),
    }
