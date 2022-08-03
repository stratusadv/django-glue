import logging, json

from django import template
from django.utils.safestring import mark_safe

from django_glue import settings

register = template.Library()


@register.inclusion_tag('django_glue/django_glue.html', takes_context=True)
def glue_init(context):
    return context


@register.simple_tag(takes_context=True)
def glue_context_data_str(context):
    return mark_safe(str(json.dumps(context[settings.DJANGO_GLUE_CONTEXT_NAME])))

