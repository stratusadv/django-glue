from django import template

register = template.Library()


@register.filter
def dashes_to_underscore(value):
    return value.replace('-', '_')


@register.filter
def spaces_to_underscore(value):
    return value.replace(' ', '_')


@register.filter
def dashes_and_spaces_to_underscore(value):
    return spaces_to_underscore(dashes_to_underscore(value))


@register.filter
def underscores_to_spaces(value):
    return value.replace('_', ' ')