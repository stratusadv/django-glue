import json

from django_glue import settings, __version__


def glue(request):
    return {
        'django_glue_url': settings.DJANGO_GLUE_URL,
        'django_glue_version': __version__,
        'django_glue_attribute_prefix': settings.DJANGO_GLUE_ATTRIBUTE_PREFIX,
        settings.DJANGO_GLUE_CONTEXT_NAME: request.session[settings.DJANGO_GLUE_SESSION_NAME]['context'],
    }
