import re
from typing import cast, TYPE_CHECKING

from django import template
from django.urls import get_resolver

from django_glue.glue.context import GlueContextManager

if TYPE_CHECKING:
    from django.http import HttpRequest

register = template.Library()


def _get_url_pattern_template(name: str) -> str:
    """
    Get the URL pattern template for a named URL.

    Walks the URL resolver tree to find the pattern, then converts
    Django URL parameters to JavaScript template literal syntax.
    """
    resolver = get_resolver()

    def find_pattern(resolver, namespace_parts, url_name):
        if namespace_parts:
            ns = namespace_parts[0]
            remaining = namespace_parts[1:]
            for pattern in resolver.url_patterns:
                if hasattr(pattern, 'namespace') and pattern.namespace == ns:
                    result = find_pattern(pattern, remaining, url_name)
                    if result:
                        prefix = str(pattern.pattern)
                        return prefix + result
            return None
        else:
            for pattern in resolver.url_patterns:
                if hasattr(pattern, 'name') and pattern.name == url_name:
                    route = str(pattern.pattern)
                    # Convert <type:name> or <name> to ${name}
                    route = re.sub(r'<(\w+:)?(\w+)>', r'${\2}', route)
                    return route
            return None

    parts = name.split(':')
    url_name = parts[-1]
    namespace_parts = parts[:-1]

    result = find_pattern(resolver, namespace_parts, url_name)
    if result is None:
        from django.urls import NoReverseMatch
        raise NoReverseMatch(f"Reverse for '{name}' not found.")

    return '/' + result


@register.simple_tag
def glue_url(name: str, **kwargs) -> str:
    """
    Generate a JavaScript expression that resolves to a URL.

    Args:
        name: The URL name (e.g., 'task:page:detail').
        **kwargs: JavaScript variable names for URL parameters.

    Usage in template:
        {% load django_glue %}
        <a :href="{% glue_url 'task:page:detail' pk='item.id' %}">View</a>

        Outputs: resolveUrl('/task/${pk}/detail/', {pk: item.id})

        Or without kwargs:
        <a href="{% glue_url 'task:page:list' %}">List</a>

        Outputs: '/task/list/'
    """
    pattern = _get_url_pattern_template(name)

    if not kwargs:
        return f"'{pattern}'"

    js_kwargs = ', '.join(f'{k}: {v}' for k, v in kwargs.items())
    return f"resolveUrl('{pattern}', {{{js_kwargs}}})"


@register.filter
def glue_field_value_path(value: str) -> str:
    return value.replace('.$fields.', '.')


@register.filter
def glue_field_metadata_path(value: str) -> str:
    if '.$fields.' in value:
        return value

    owner, field_name = value.rsplit('.', 1)
    return f'{owner}.$fields.{field_name}'


@register.inclusion_tag('django_glue/django_glue.html', takes_context=True)
def django_glue_init(context: dict) -> dict:
    request = cast('HttpRequest', context.get('request'))

    for key, val in GlueContextManager(request).context_data.items():
        context[key] = val  # noqa: PERF403

    return context
