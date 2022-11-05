from django_glue.conf import settings
from django_glue import __version__


def glue(request):
    return {
        'DJANGO_GLUE_URL': settings.DJANGO_GLUE_URL,
        'DJANGO_GLUE_VERSION': __version__,
        settings.DJANGO_GLUE_CONTEXT_NAME: request.session[settings.DJANGO_GLUE_SESSION_NAME].get('context'),
        settings.DJANGO_GLUE_KEEP_LIVE_CONTEXT_NAME: request.session[settings.DJANGO_GLUE_KEEP_LIVE_SESSION_NAME],
    }
