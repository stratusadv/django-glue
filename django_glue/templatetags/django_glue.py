from typing import cast, TYPE_CHECKING

from django import template

from django_glue.glue.context import GlueContextManager

if TYPE_CHECKING:
    from django.http import HttpRequest

register = template.Library()


@register.inclusion_tag('django_glue/django_glue.html', takes_context=True)
def django_glue_init(context: dict) -> dict:
    request = cast('HttpRequest', context.get('request'))

    for key, val in GlueContextManager(request).context_data.items():
        context[key] = val  # noqa: PERF403

    return context
