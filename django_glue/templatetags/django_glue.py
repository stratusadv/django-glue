import logging

from django import template
from django.utils.safestring import mark_safe

from django_glue import settings
from django_glue.utils import GLUE_UPDATE_TYPES, GLUE_ACCESS_TYPES, generate_safe_glue_attribute_string

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


@register.simple_tag(takes_context=True)
def glue_connect(context, unique_name, field, update='none', access='view'):
    if access not in GLUE_ACCESS_TYPES:
        raise ValueError(f'access "{access}" is not valid, choices are {GLUE_ACCESS_TYPES}')

    is_valid_connection = False

    field_value = None
    if unique_name in context[settings.DJANGO_GLUE_CONTEXT_NAME]:
        if field in context[settings.DJANGO_GLUE_CONTEXT_NAME][unique_name]['fields']:
            field_value = context[settings.DJANGO_GLUE_CONTEXT_NAME][unique_name]['fields'][field]['value']
            is_valid_connection = True

    if is_valid_connection:
        return generate_safe_glue_attribute_string(
            unique_name=unique_name,
            connection=context[settings.DJANGO_GLUE_CONTEXT_NAME][unique_name]['connection'],
            update=update,
            field_name=field,
            field_value=field_value,
        )
    else:
        return mark_safe(f'')


def glue_connect_submit(context, submit_action, unique_name):
    return generate_safe_glue_attribute_string(
        unique_name=unique_name,
        connection=context[settings.DJANGO_GLUE_CONTEXT_NAME][unique_name]['connection'],
        action=submit_action,
    )


@register.simple_tag(takes_context=True)
def glue_event(context, unique_name, event, update):
    return generate_safe_glue_attribute_string(unique_name=unique_name, category=context["glue"][unique_name]["type"],
                                               update=update, event=event)


class GlueQuerySetComponentListDisplayNode(template.Node):
    def __init__(self, unique_name, component_template_name):
        self.unique_name = unique_name
        self.component_template_name = component_template_name

    def render(self, context):
        from django.template import loader
        return mark_safe(
            f'<div {generate_safe_glue_attribute_string(unique_name=self.unique_name, connection="query_set", action="list_display")}>{loader.get_template(self.component_template_name).render(context.flatten())}</div>')


@register.tag
def glue_query_set_component_list_display(parser, token):
    try:
        tag_name, unique_name, component_template_name = token.split_contents()
    except ValueError:
        raise template.TemplateSyntaxError(f'{token.split_contents()[0]} tag requires exactly two arguments')

    return GlueQuerySetComponentListDisplayNode(unique_name[1:-1], component_template_name[1:-1])


@register.simple_tag(takes_context=True)
def glue_submit_update(context, unique_name):
    return glue_connect_submit(context, 'submit_update', unique_name)


@register.simple_tag(takes_context=True)
def glue_submit_create(context, unique_name):
    return glue_connect_submit(context, 'submit_create', unique_name)


class GlueComponentNode(template.Node):
    def __init__(self, node_list, component_name, id_field_name):
        self.component_name = component_name
        self.id_field_name = id_field_name
        self.node_list = node_list

    def render(self, context):
        output = self.node_list.render(context)
        try:
            return mark_safe(f'''
            <template {generate_safe_glue_attribute_string(component=self.component_name, id_field=self.id_field_name)}>
            <section {generate_safe_glue_attribute_string(id='')}>
            {output}
            </section>
            </template>
                             ''')
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
def glue_component_value(field):
    return generate_safe_glue_attribute_string(component_field=field)


@register.simple_tag(takes_context=True)
def glue_component_event(context, event, action):
    return generate_safe_glue_attribute_string(event=event, action=action)
