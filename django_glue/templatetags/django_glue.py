import logging

from django import template
from django.utils.safestring import mark_safe

# from django_glue.utils import convert_glue_dict_to_json

register = template.Library()


@register.inclusion_tag('django_glue/django_glue.html', takes_context=True, name='glue_init')
def glue_init(context):
    context['glue_json_string'] = context['glue']
    return context


@register.inclusion_tag('django_glue/message_list.html', name='glue_message')
def glue_message():
    return None


@register.inclusion_tag('django_glue/message_list_viewport.html', name='glue_message_viewport')
def glue_message_viewport():
    return None


@register.simple_tag(takes_context=True, name='glue_connect')
def glue_connect(context, type, unique_name_and_field_string, custom_attributes=''):
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
        field_value = context["glue"][unique_name]["fields"][field_name]["value"]
        return mark_safe(f'glue-connect="{type}" glue-unique-name="{ unique_name }" glue-field-name="{ field_name }" glue-field-value="{ field_value }" {custom_attributes}')
    else:
        return mark_safe(f'')


@register.simple_tag(takes_context=True, name='glue_input')
def glue_input(context, unique_name_and_field_string):
    return glue_connect(context, 'input', unique_name_and_field_string)


@register.simple_tag(takes_context=True, name='glue_textarea')
def glue_textarea(context, unique_name_and_field_string):
    return glue_connect(context, 'input', unique_name_and_field_string)


@register.simple_tag(takes_context=True, name='glue_textarea')
def glue_submit(context, unique_name_and_field_string):
    return glue_connect(context, 'submit', unique_name_and_field_string)
