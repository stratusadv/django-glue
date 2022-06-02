import logging

from django import template
from django.utils.safestring import mark_safe

# from django_glue.utils import convert_glue_dict_to_json

register = template.Library()


@register.inclusion_tag('glue_js.html', takes_context=True, name='glue_js')
def glue_js(context):
    context['glue_json_string'] = context['glue']
    return context


@register.simple_tag(takes_context=True, name='glue_connect')
def glue_connect(context, unique_name_and_field_string):
    connect_list = unique_name_and_field_string.split('.')

    is_valid_connection = False
    unique_name = ''
    field_name = ''

    if len(connect_list) == 2:
        unique_name = connect_list[0]
        field_name = connect_list[1]

        if unique_name in context['glue']:
            if field_name in context['glue'][unique_name]['fields']:
                is_valid_connection = True

    if is_valid_connection:
        return mark_safe(f'glue-connect glue-unique-name="{ unique_name }" glue-field-name="{ field_name }"')
    else:
        return mark_safe(f'')