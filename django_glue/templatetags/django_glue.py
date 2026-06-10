from django import template
from django_glue.conf import settings

from django_glue import constants
from django_glue.session import GlueSession

register = template.Library()


@register.inclusion_tag('django_glue/django_glue.html', takes_context=True)
def django_glue_init(context: dict) -> dict:
    request = context.get('request')

    if request:
        context[constants.DJANGO_GLUE_URLS_KEY] = {
            constants.ACTION_URL_NAME: f'/{constants.BASE_URL_NAME}/{constants.ACTION_URL_NAME}/',
            constants.KEEP_LIVE_URL_NAME: f'/{constants.BASE_URL_NAME}/{constants.KEEP_LIVE_URL_NAME}/',
            constants.GLUE_VIEW_URL_NAME: f'/{constants.BASE_URL_NAME}/{constants.GLUE_VIEW_URL_NAME}/',
        }
        context[constants.DJANGO_GLUE_VERSION_KEY] = constants.__VERSION__
        context[constants.DJANGO_GLUE_KEEP_LIVE_INTERVAL_TIME_SECONDS_KEY] = (
            settings.DJANGO_GLUE_KEEP_LIVE_INTERVAL_TIME_SECONDS
        )
        context[constants.DJANGO_GLUE_SESSION_PROXY_REGISTRY_KEY] = GlueSession(
            request
        ).proxy_registry
        context[constants.DJANGO_GLUE_PROXIES_CONTEXT_DATA_KEY] = {}
        context[constants.DJANGO_SESSION_EXPIRY_MESSAGE_KEY] = (
            settings.DJANGO_GLUE_SESSION_EXPIRY_MESSAGE
        )

        if hasattr(request, '__glue_context_data__'):
            context[constants.DJANGO_GLUE_PROXIES_CONTEXT_DATA_KEY] = request.__glue_context_data__

    return context
