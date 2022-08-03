import json

from django_glue import settings, __version__


def glue(request):
    return {
        'DJANGO_GLUE_URL': settings.DJANGO_GLUE_URL,
        'DJANGO_GLUE_VERSION': __version__,
        settings.DJANGO_GLUE_CONTEXT_NAME: request.session[settings.DJANGO_GLUE_SESSION_NAME]['context'],
    }
