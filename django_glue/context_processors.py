from django_glue.utils import generate_glue_dict
from django.conf import settings


def glue(request):
    if settings.DJANGO_GLUE_URL:
        glue_url = settings.DJANGO_GLUE_URL
    else:
        glue_url = 'django_glue/'
    return {
        'glue_url': glue_url,
        'glue': generate_glue_dict(),
    }
