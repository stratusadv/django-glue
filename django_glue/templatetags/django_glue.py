import logging

from django import template
from django.utils.safestring import mark_safe

from django_glue.utils import convert_glue_dict_to_json

register = template.Library()


@register.inclusion_tag('glue_js.html', takes_context=True, name='glue_js')
def glue_js(context):
    context['glue_json_string'] = convert_glue_dict_to_json(context['glue'])
    return context


@register.simple_tag(takes_context=True, name='glue_connect')
def glue_connect(context, target_string):
    target_key_list = target_string.split('.')
    glue_key = ''
    if len(target_key_list) == 3:

        glue_type = target_key_list[0]
        glue_object = target_key_list[1]
        glue_field = target_key_list[2]

        if glue_type in context['glue']:
            if glue_object in context['glue'][glue_type]:
                if glue_type == 'fields':
                    if glue_field in context['glue'][glue_type][glue_object]:
                        glue_key = context['glue'][glue_type][glue_object]['django_glue_key']
                elif glue_type == 'objects':
                    glue_key = context['glue'][glue_type][glue_object]['django_glue_key']
        return mark_safe(f'glue-connect glue-key="{ glue_key }" glue-type="{ glue_type }" glue-object="{ glue_object }" glue-field="{ glue_field }"')
    else:
        return mark_safe(f'')