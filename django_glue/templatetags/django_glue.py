import logging, json

from django import template
from django.template.defaultfilters import stringfilter
from django.utils.safestring import mark_safe

from django_glue.conf import settings

register = template.Library()


@register.inclusion_tag('django_glue/django_glue.html', takes_context=True)
def glue_init(context):
    return context


@register.inclusion_tag('django_glue/django_glue_core.html', takes_context=True)
def glue_init_core(context):
    return context


@register.simple_tag(takes_context=True)
def glue_context_data_str(context):
    return mark_safe(str(json.dumps(context[settings.DJANGO_GLUE_CONTEXT_NAME])))


@register.simple_tag(takes_context=True)
def glue_context_keep_live_str(context):
    return mark_safe(str(json.dumps(context[settings.DJANGO_GLUE_KEEP_LIVE_CONTEXT_NAME])))


@register.tag
def glue_html_attr(parser, token):
    try:
        tokens = token.contents.split(None, 1)
        unique_name, field = tokens[1].split('.', 1)
    except ValueError:
        raise template.TemplateSyntaxError(f'{token.contents.split()[0]} tag requires arguments')

    return GlueHTMLAttrNode(unique_name, field)


class GlueHTMLAttrNode(template.Node):
    def __init__(self, unique_name, field):
        self.unique_name = unique_name
        self.field = field

    def render(self, context):
        html_attr_str = ''

        for key, val in context[settings.DJANGO_GLUE_CONTEXT_NAME][self.unique_name]['fields'][self.field]['html_attr'].items():
            html_attr_str = f'{key}="{val}" '

        return html_attr_str