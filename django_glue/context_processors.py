import json

from django.conf import settings

from django_glue.utils import GLUE_SESSION_NAME
import django_glue


def glue(request):
    if settings.DJANGO_GLUE_URL:
        django_glue_url = settings.DJANGO_GLUE_URL
    else:
        django_glue_url = 'django_glue/'

    return {
        'django_glue_url': django_glue_url,
        'django_glue_version': django_glue.__version__,
        'glue': request.session[GLUE_SESSION_NAME]['context'],
    }
