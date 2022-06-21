import json

from django.conf import settings

from django_glue.utils import GLUE_SESSION_NAME

def glue(request):
    if settings.DJANGO_GLUE_URL:
        glue_url = settings.DJANGO_GLUE_URL
    else:
        glue_url = 'django_glue/'

    return {
        'glue_url': glue_url,
        'glue': request.session[GLUE_SESSION_NAME]['context'],
    }
