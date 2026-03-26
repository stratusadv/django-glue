from django import template

register = template.Library()


@register.simple_tag
def split_glue_binding(binding):
    """
    Splits a 'proxy.field' binding string into a dict with proxy and field.

    Usage:
        {% glue_binding "gorilla.name" as b %}
        {% include "components/glue_text_input.html" with proxy=b.proxy field=b.field %}

    Or more concisely with the include:
        {% glue_binding "gorilla.name" as b %}
        <input x-model="{{ b.proxy }}.{{ b.field }}">
    """
    parts = binding.split('.')
    if len(parts) != 2:
        raise ValueError(f"binding must be 'proxy.field', got '{binding}'")

    return {
        'obj': parts[0],
        'field': parts[1],
    }
