from django import template

register = template.Library()


@register.filter
def is_dict(value):
    return isinstance(value, dict)


@register.filter
def is_not_dict(value):
    return not is_dict(value)


@register.filter
def is_list(value):
    return isinstance(value, list)


@register.filter
def is_not_list(value):
    return not is_list(value)


@register.filter
def is_list_or_tuple(value):
    return isinstance(value, (list, tuple))


@register.filter
def is_not_list_or_tuple(value):
    return not is_list_or_tuple(value)


@register.filter
def is_tuple(value):
    return isinstance(value, tuple)


@register.filter
def is_not_tuple(value):
    return not is_tuple(value)