from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.template import Context, Node, TemplateSyntaxError
from django.template.loader import get_template
from django.utils.safestring import mark_safe

from django_glue.access import GlueAccess
from django_glue.exceptions import GlueComponentKeyError
from django_glue.glue import address
from django_glue.glue.component_naming import canonical_key, component_name
from django_glue.glue.component_registry import component_registry
from django_glue.glue.context import GlueContextManager
from django_glue.glue.component_root import inject_component_root

if TYPE_CHECKING:
    from django.template.base import FilterExpression, Parser, Token


STAMPED_KEYS_ATTR = '_django_glue_stamped_component_keys'


class GlueComponentNode(Node):
    def __init__(
        self,
        tag_expression: FilterExpression,
        parameters: dict[str, FilterExpression],
        key_expression: FilterExpression | None,
        access_expression: FilterExpression | None,
    ) -> None:
        self.tag_expression = tag_expression
        self.parameters = parameters
        self.key_expression = key_expression
        self.access_expression = access_expression

    def render(self, context: Context) -> str:
        request = getattr(context, 'request', None) or context.get('request')
        if request is None:
            raise GlueComponentKeyError(
                '{% glue_component %} needs a request in the template context.'
            )

        tag_name = self.tag_expression.resolve(context)
        component_class = component_registry.from_tag_name(tag_name)
        key = self.key_expression.resolve(context) if self.key_expression else None
        if key is None and context.get('forloop') is not None:
            raise GlueComponentKeyError(
                f"{{% glue_component '{tag_name}' %}} needs a stable key inside a loop."
            )
        canonical = canonical_key(key)
        parent = context.get('component')
        parent_address = parent.address if parent is not None else ''
        name = component_name(parent_address, tag_name, key)
        stamped = request.__dict__.setdefault(STAMPED_KEYS_ATTR, set())
        identity = (parent_address, tag_name, canonical)
        if identity in stamped:
            raise GlueComponentKeyError(
                f"Two '{tag_name}' components share key {canonical} under one parent."
            )
        stamped.add(identity)

        component = component_class(
            name=name,
            access=(
                GlueAccess(self.access_expression.resolve(context))
                if self.access_expression is not None
                else GlueAccess.VIEW
            ),
            **{key: expression.resolve(context) for key, expression in self.parameters.items()},
        )
        if parent is not None:
            component._address = address.item(parent_address, f'{tag_name}:{canonical}')
        GlueContextManager(request).add_glue(component)
        template = get_template(component.template)
        with context.push(**component.get_context_data()):
            html = template.template.render(context)
        return mark_safe(inject_component_root(
            html,
            component.address,
            component.template,
            [component.entry.model_dump(), *component._serialized_child_entries()],
        ))


def register_component_tags(register: Any) -> None:
    def parse_component_token(parser: Parser, token: Token) -> GlueComponentNode:
        bits = token.split_contents()
        if len(bits) < 2:
            raise TemplateSyntaxError('{% glue_component %} needs a registered tag name.')
        tag_expression = parser.compile_filter(bits[1])
        parameters: dict[str, FilterExpression] = {}
        key_expression = None
        access_expression = None
        seen: set[str] = set()
        for bit in bits[2:]:
            key, separator, raw_value = bit.partition('=')
            if not separator or not raw_value:
                raise TemplateSyntaxError(
                    '{% glue_component %} accepts keyword arguments after the tag name.'
                )
            if key in seen:
                raise TemplateSyntaxError(f'Duplicate component argument: {key!r}.')
            seen.add(key)
            expression = parser.compile_filter(raw_value)
            if key == 'key':
                if raw_value.strip('"\'') in {'forloop.counter', 'forloop.counter0'}:
                    raise TemplateSyntaxError('A component cannot use a loop index as its key.')
                key_expression = expression
            elif key == 'access':
                access_expression = expression
            else:
                parameters[key] = expression
        return GlueComponentNode(tag_expression, parameters, key_expression, access_expression)

    def reject_end_tag(parser: Parser, token: Token) -> Node:
        _ = parser, token
        raise TemplateSyntaxError('Component slots are not supported; omit endglue_component.')

    register.tag('glue_component', parse_component_token)
    register.tag('endglue_component', reject_end_tag)
