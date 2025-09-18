from django import template
import json

register = template.Library()

@register.filter(name='json_loads')
def json_loads(value):
    try:
        return json.loads(value)
    except (TypeError, ValueError) as e:
        return {}