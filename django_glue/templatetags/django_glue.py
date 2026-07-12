from django import template
from django_glue.conf import settings

from django_glue import constants

register = template.Library()


@register.inclusion_tag('django_glue/django_glue.html', takes_context=True)
def django_glue_init(context: dict) -> dict:
    request = context.get('request')

    if request:
        context[constants.DJANGO_GLUE_URLS_KEY] = {
            constants.BOUND_ATTRIBUTE_EVENT_URL_NAME: f'/{constants.BASE_URL_NAME}/{constants.BOUND_ATTRIBUTE_EVENT_URL_NAME}/',
            constants.GLUE_VIEW_URL_NAME: f'/{constants.BASE_URL_NAME}/{constants.GLUE_VIEW_URL_NAME}/',
        }
        context[constants.DJANGO_GLUE_VERSION_KEY] = constants.__VERSION__
        context[constants.DJANGO_GLUE_KEEP_LIVE_INTERVAL_TIME_SECONDS_KEY] = (
            settings.DJANGO_GLUE_KEEP_LIVE_INTERVAL_TIME_SECONDS
        )
        context[constants.DJANGO_GLUE_PROXIES_SCRIPT_NAME_KEY] = constants.DJANGO_GLUE_PROXIES_SCRIPT_NAME

        context[constants.DJANGO_GLUE_PROXIES_KEY] = {}

        if hasattr(request, constants.DJANGO_GLUE_PROXIES_REQUEST_ATTR_KEY):
            context[constants.DJANGO_GLUE_PROXIES_KEY] = getattr(
                request,
                constants.DJANGO_GLUE_PROXIES_REQUEST_ATTR_KEY
            )

    return context
