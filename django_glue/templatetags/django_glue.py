import logging

from django import template
from django.utils.safestring import mark_safe

from django_glue.utils import GLUE_CONNECT_INPUT_METHODS, GLUE_CONNECT_INPUT_TYPES, GLUE_CONNECT_SUBMIT_METHODS

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


def glue_connect_input(context, input_type, input_method, unique_name_and_field_string, custom_attributes=''):
    if input_type not in GLUE_CONNECT_INPUT_TYPES:
        raise ValueError(f'input_type "{input_type}" is not valid, choices are {GLUE_CONNECT_INPUT_TYPES}')

    if input_method not in GLUE_CONNECT_INPUT_METHODS:
        raise ValueError(f'input_method "{input_method}" is not valid, choices are {GLUE_CONNECT_INPUT_METHODS}')

    connect_list = unique_name_and_field_string.split('.')

    is_valid_connection = False

    unique_name = ''

    field_name = ''
    field_value = ''

    if len(connect_list) == 2:
        unique_name = connect_list[0]
        field_name = connect_list[1]

        if unique_name in context['glue']:
            if field_name in context['glue'][unique_name]['fields']:
                field_value = context['glue'][unique_name]['fields'][field_name]['value']
                is_valid_connection = True

    if is_valid_connection:
        return mark_safe(f'glue-connect="{input_type}" glue-type="{context["glue"][unique_name]["type"]}" glue-method="{input_method}" glue-unique-name="{unique_name}" glue-field-name="{field_name}" glue-field-value="{field_value}" {custom_attributes}')
    else:
        return mark_safe(f'')


def glue_connect_submit(context, submit_method, unique_name, custom_attributes=''):
    if submit_method not in GLUE_CONNECT_SUBMIT_METHODS:
        raise ValueError(f'submit_method "{submit_method}" is not valid, choices are {GLUE_CONNECT_SUBMIT_METHODS}')

    return mark_safe(f'glue-connect="submit" glue-method="{submit_method}" glue-unique-name="{unique_name}" {custom_attributes}')


@register.simple_tag(takes_context=True, name='glue_input_live')
def glue_input_live(context, unique_name_and_field_string):
    return glue_connect_input(context, 'input', 'live', unique_name_and_field_string)


@register.simple_tag(takes_context=True, name='glue_input_form')
def glue_input_form(context, unique_name_and_field_string):
    return glue_connect_input(context, 'input', 'form', unique_name_and_field_string)


@register.simple_tag(takes_context=True, name='glue_query_set_display')
def glue_query_set_display(context, unique_name):
    return None


@register.simple_tag(takes_context=True, name='glue_textarea_live')
def glue_textarea_live(context, unique_name_and_field_string):
    return glue_connect_input(context, 'textarea', 'live', unique_name_and_field_string)


@register.simple_tag(takes_context=True, name='glue_textarea_form')
def glue_textarea_form(context, unique_name_and_field_string):
    return glue_connect_input(context, 'textarea', 'form', unique_name_and_field_string)


@register.simple_tag(takes_context=True, name='glue_submit_update')
def glue_submit_update(context, unique_name):
    return glue_connect_submit(context, 'update', unique_name)


@register.simple_tag(takes_context=True, name='glue_submit_create')
def glue_submit_create(context, unique_name):
    return glue_connect_submit(context, 'create', unique_name)

