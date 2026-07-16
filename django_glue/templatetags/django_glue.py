from django import template

from django_glue import constants
from django_glue.context import GlueContext

register = template.Library()


@register.inclusion_tag('django_glue/django_glue.html', takes_context=True)
def django_glue_init(context: dict) -> dict:
    request = context.get('request')

    manifest_list = []

    if request and hasattr(request, constants.DJANGO_GLUE_MANIFEST_REQUEST_ATTR_KEY):
        manifest_list = getattr(
            request,
            constants.DJANGO_GLUE_MANIFEST_REQUEST_ATTR_KEY,
            []
        )

    context[constants.DJANGO_GLUE_CONTEXT_KEY] = GlueContext.from_manifest_list(manifest_list).model_dump()
    context[constants.DJANGO_GLUE_VERSION_KEY] = constants.__VERSION__
    context[constants.DJANGO_GLUE_CONTEXT_SCRIPT_NAME_KEY] = constants.DJANGO_GLUE_CONTEXT_SCRIPT_NAME

    return context
