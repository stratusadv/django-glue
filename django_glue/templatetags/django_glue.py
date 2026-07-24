from typing import cast, TYPE_CHECKING

from django import template

from django_glue.glue.context import GlueContextManager

if TYPE_CHECKING:
    from django.http import HttpRequest

register = template.Library()


@register.filter
def glue_field_value_path(value: str) -> str:
    return value.replace('.$fields.', '.')


@register.filter
def glue_field_metadata_path(value: str) -> str:
    if '.$fields.' in value:
        return value

    owner, field_name = value.rsplit('.', 1)
    return f'{owner}.$fields.{field_name}'


@register.inclusion_tag('django_glue/django_glue.html', takes_context=True)
def django_glue_init(context: dict) -> dict:
    request = cast('HttpRequest', context.get('request'))

    for key, val in GlueContextManager(request).context_data.items():
        context[key] = val  # noqa: PERF403

    return context
