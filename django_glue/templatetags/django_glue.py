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
def glue_connect(context, target):
    target_key_list = target.split('.')
    value = ''
    if len(target_key_list) == 3:
        if target_key_list[0] in context['glue']:
            if target_key_list[1] in context['glue'][target_key_list[0]]:
                if target_key_list[0] == 'fields':
                    if target_key_list[2] in context['glue'][target_key_list[0]][target_key_list[1]]:
                        value = context['glue'][target_key_list[0]][target_key_list[1]][target_key_list[2]]
                elif target_key_list[0] == 'objects':
                    value = context['glue'][target_key_list[0]][target_key_list[1]]['data'].__dict__[target_key_list[2]]
        return mark_safe(f'id="{target_key_list[2]}" name="{target_key_list[2]}"')
    else:
        return mark_safe(f'')