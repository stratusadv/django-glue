import logging

from django import template
from django.utils.safestring import mark_safe

from django_glue import settings
from django_glue.utils import GLUE_UPDATE_TYPES, GLUE_ACCESS_TYPES, GLUE_FORM_SUBMIT_TYPES, generate_safe_glue_attribute_string

register = template.Library()


@register.inclusion_tag('django_glue/django_glue.html', takes_context=True)
def glue_init(context):
    return context


@register.inclusion_tag('django_glue/message_list.html')
def glue_message():
    return None


@register.inclusion_tag('django_glue/message_list_viewport.html')
def glue_message_viewport():
    return None


def glue_connect_input(context, input_method, unique_name_and_field_string, custom_attributes=''):

    if input_method not in GLUE_ACCESS_TYPES:
        raise ValueError(f'input_method "{input_method}" is not valid, choices are {GLUE_ACCESS_TYPES}')

    connect_list = unique_name_and_field_string.split('.')

    is_valid_connection = False

    unique_name = ''

    field_name = ''
    field_value = ''

    if len(connect_list) == 2:
        unique_name = connect_list[0]
        field_name = connect_list[1]

        if unique_name in context[settings.DJANGO_GLUE_CONTEXT_NAME]:
            if field_name in context[settings.DJANGO_GLUE_CONTEXT_NAME][unique_name]['fields']:
                field_value = context[settings.DJANGO_GLUE_CONTEXT_NAME][unique_name]['fields'][field_name]['value']
                is_valid_connection = True

    if is_valid_connection:
        return mark_safe(f'glue-connect="{input_type}" glue-type="{context["glue"][unique_name]["type"]}" glue-method="{input_method}" glue-unique-name="{unique_name}" glue-field-name="{field_name}" glue-field-value="{field_value}" {custom_attributes}')
    else:
        return mark_safe(f'')


def glue_connect_query_set(context, unique_name):
    return mark_safe(f'glue-connect="query_set" glue-type="{context["glue"][unique_name]["type"]}" glue-unique-name="{unique_name}"')


def glue_connect_submit(context, submit_method, unique_name, custom_attributes=''):
    if submit_method not in GLUE_FORM_SUBMIT_TYPES:
        raise ValueError(f'submit_method "{submit_method}" is not valid, choices are {GLUE_FORM_SUBMIT_TYPES}')

    return mark_safe(f'glue-connect="submit" glue-type="{context["glue"][unique_name]["type"]}" glue-method="{submit_method}" glue-unique-name="{unique_name}" {custom_attributes}')


@register.simple_tag(takes_context=True)
def glue_event(context, unique_name, event, update):
    return generate_safe_glue_attribute_string(unique_name=unique_name, category=context["glue"][unique_name]["type"], update=update, event=event)


@register.simple_tag(takes_context=True)
def glue_input_live(context, unique_name_and_field_string):
    return glue_connect_input(context, 'input', 'live', unique_name_and_field_string)


@register.simple_tag(takes_context=True)
def glue_input_form(context, unique_name_and_field_string):
    return glue_connect_input(context, 'input', 'form', unique_name_and_field_string)


@register.simple_tag(takes_context=True)
def glue_live(context, unique_name_and_field_string):
    return glue_connect_input(context, 'input', 'live', unique_name_and_field_string)


class GlueQuerySetComponentDisplayNode(template.Node):
    def __init__(self, unique_name, component_name):
        self.unique_name = unique_name
        self.component_name = component_name

    def render(self, context):
        from django.template import loader
        return mark_safe(f'<div glue-connect="query_set" glue-type="query_set" glue-template-display="{self.unique_name}" glue-unique-name="{self.unique_name}">{loader.get_template(self.template_name).render(context.flatten())}</div>')


@register.tag
def glue_query_set_component_display(parser, token):
    try:
        tag_name, unique_name, template_name = token.split_contents()
    except ValueError:
        raise template.TemplateSyntaxError(f'{token.split_contents()[0]} tag requires exactly two arguments')

    return GlueQuerySetComponentDisplayNode(unique_name[1:-1], template_name[1:-1])


@register.simple_tag(takes_context=True)
def glue_textarea_live(context, unique_name_and_field_string):
    return glue_connect_input(context, 'textarea', 'live', unique_name_and_field_string)


@register.simple_tag(takes_context=True)
def glue_textarea_form(context, unique_name_and_field_string):
    return glue_connect_input(context, 'textarea', 'form', unique_name_and_field_string)


@register.simple_tag(takes_context=True)
def glue_submit_update(context, unique_name):
    return glue_connect_submit(context, 'update', unique_name)


@register.simple_tag(takes_context=True)
def glue_submit_create(context, unique_name):
    return glue_connect_submit(context, 'create', unique_name)


class GlueComponentNode(template.Node):
    def __init__(self, node_list, component_name, id_field_name):
        self.template_name = component_name
        self.id_field_name = id_field_name
        self.node_list = node_list

    def render(self, context):
        output = self.node_list.render(context)
        try:
            return mark_safe(f'<template glue-template="{self.template_name}" glue-id-field="{self.id_field_name}">{output}</template>')
        except template.VariableDoesNotExist:
            return ''


@register.tag
def glue_component(parser, token):
    node_list = parser.parse(('end_glue_component',))
    parser.delete_first_token()
    try:
        tag_name, component_name, id_field_name = token.split_contents()
    except ValueError:
        raise template.TemplateSyntaxError(f'{token.split_contents()[0]} tag requires exactly two arguments')

    return GlueComponentNode(node_list, component_name[1:-1], id_field_name[1:-1])


@register.simple_tag
def glue_component_value(model_name_and_field):
    return generate_safe_glue_attribute_string(template_value=model_name_and_field)


@register.simple_tag(takes_context=True)
def glue_component_event(context, unique_name, event, update):
    return generate_safe_glue_attribute_string(unique_name=unique_name, category=context["glue"][unique_name]["type"], update=update, event=event)
