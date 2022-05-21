import logging

from django import template

from django_glue.utils import convert_glue_dict_to_json

register = template.Library()


@register.inclusion_tag('glue_js.html', takes_context=True, name='glue_js')
def glue_js(context):
    context['glue_json_string'] = convert_glue_dict_to_json(context['glue'])
    return context
