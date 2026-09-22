from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.template import Context, Node, TemplateSyntaxError
from django.template.loader import get_template
from django.utils.safestring import mark_safe

from django_glue.access import GlueAccess
from django_glue.exceptions import GlueComponentKeyError
from django_glue.glue.component.naming import canonical_key, derive_component_name
from django_glue.glue.component.registry import glue_component_registry

if TYPE_CHECKING:
    from django.template.base import FilterExpression, Parser, Token

TAG_NAME = 'glue_component'
END_TAG_NAME = f'end{TAG_NAME}'

RESERVED_ARGUMENTS = frozenset({'key', 'access'})
REJECTED_KEY_SOURCES = frozenset({'forloop.counter', 'forloop.counter0'})

_STAMPED_KEYS_ATTR = '_django_glue_stamped_component_keys'


class GlueComponentNode(Node):
    """Stamps a registered component and renders it in place.

    The component registers as its own top-level manifest rather than as a child
    of the enclosing component: a tag inside a ``{% for %}`` is not a class
    attribute and cannot be discovered by the static attribute collector. Parent
    and child are related by template, not by policy. See
    design/components/spec.md §6.
    """

    def __init__(
        self,
        tag_name_expression: FilterExpression,
        parameter_expressions: dict[str, FilterExpression],
        key_expression: FilterExpression | None,
        access_expression: FilterExpression | None,
    ) -> None:
        self.tag_name_expression = tag_name_expression
        self.parameter_expressions = parameter_expressions
        self.key_expression = key_expression
        self.access_expression = access_expression

    def render(self, context: Context) -> str:
        request = self._resolve_request(context)
        tag_name = self.tag_name_expression.resolve(context)
        component_class = glue_component_registry.get(tag_name)

        key = self._resolve_key(context, tag_name)
        parent_name = self._resolve_parent_name(context)
        name = derive_component_name(
            parent_name=parent_name,
            tag_name=tag_name,
            key=key,
        )

        self._reject_duplicate(request, parent_name, tag_name, key, name)

        component = component_class(
            name=name,
            access=self._resolve_access(context),
            **{
                parameter_name: expression.resolve(context)
                for parameter_name, expression in self.parameter_expressions.items()
            },
        )

        # A component carries its own manifest on its root element rather than
        # joining the page's manifest_list, so it is bound here directly instead
        # of through GlueContextManager.add_glue. The session still has to exist
        # before a policy can be signed.
        if not request.session.session_key:
            request.session.create()

        component.request = request
        component.mount()

        return self._render_component(component, context)

    def _render_component(self, component: Any, context: Context) -> str:
        """Render the component's template against the current context.

        The existing context is reused rather than built fresh so a nested
        ``{% glue_component %}`` sees this component as its parent, and so
        request-context template tags keep working.
        """
        template = get_template(component.template)

        with context.push(**component.get_context_data()):
            html = template.template.render(context)

        return mark_safe(component.inject_root(html))

    @staticmethod
    def _resolve_request(context: Context) -> Any:
        request = getattr(context, 'request', None) or context.get('request')

        if request is None:
            msg = (
                f'{{% {TAG_NAME} %}} needs the request in the template context. '
                f'Render with a RequestContext, or add '
                f"'django.template.context_processors.request' to your context processors."
            )
            raise GlueComponentKeyError(msg)

        return request

    @staticmethod
    def _resolve_parent_name(context: Context) -> str:
        """Read the enclosing component the owner's context data placed here."""
        parent = context.get('component')

        return parent.name if parent is not None else ''

    def _resolve_key(self, context: Context, tag_name: str) -> Any:
        if self.key_expression is not None:
            return self.key_expression.resolve(context)

        if context.get('forloop') is not None:
            msg = (
                f"{{% {TAG_NAME} '{tag_name}' %}} is inside a loop and needs key=. "
                f'Without one, every iteration derives the same name and the '
                f'stamped components collide.'
            )
            raise GlueComponentKeyError(msg)

        return None

    def _resolve_access(self, context: Context) -> GlueAccess:
        if self.access_expression is None:
            return GlueAccess.VIEW

        return GlueAccess(self.access_expression.resolve(context))

    @staticmethod
    def _reject_duplicate(
        request: Any,
        parent_name: str,
        tag_name: str,
        key: Any,
        name: str,
    ) -> None:
        stamped = getattr(request, _STAMPED_KEYS_ATTR, None)

        if stamped is None:
            stamped = set()
            setattr(request, _STAMPED_KEYS_ATTR, stamped)

        if name in stamped:
            msg = (
                f"Two '{tag_name}' components share the key "
                f'{canonical_key(key)} under the same parent. A key identifies a '
                f'child among its siblings, so it must be distinct.'
            )
            raise GlueComponentKeyError(msg)

        stamped.add(name)


def _parse_component_token(parser: Parser, token: Token) -> GlueComponentNode:
    bits = token.split_contents()

    if len(bits) < 2:
        msg = f"{{% {TAG_NAME} %}} needs a registered component tag name, e.g. {{% {TAG_NAME} 'time-entry-day' %}}."
        raise TemplateSyntaxError(msg)

    tag_name_expression = parser.compile_filter(bits[1])
    parameter_expressions: dict[str, FilterExpression] = {}
    key_expression = None
    access_expression = None

    for bit in bits[2:]:
        name, _, raw_value = bit.partition('=')

        if not raw_value:
            msg = (
                f'{{% {TAG_NAME} %}} takes the component tag name positionally and '
                f"everything else as keywords; got '{bit}'."
            )
            raise TemplateSyntaxError(msg)

        if name in parameter_expressions or (name == 'key' and key_expression):
            msg = f"{{% {TAG_NAME} %}} got a duplicate argument '{name}'."
            raise TemplateSyntaxError(msg)

        expression = parser.compile_filter(raw_value)

        if name == 'key':
            _reject_loop_index_key(raw_value)
            key_expression = expression
        elif name == 'access':
            access_expression = expression
        else:
            parameter_expressions[name] = expression

    return GlueComponentNode(
        tag_name_expression,
        parameter_expressions,
        key_expression,
        access_expression,
    )


def _reject_loop_index_key(raw_value: str) -> None:
    if raw_value.strip('"\'') in REJECTED_KEY_SOURCES:
        msg = (
            f'{{% {TAG_NAME} %}} cannot key on a loop index. A key must stay the '
            f'same for the same logical child across renders; a position does not, '
            f'so inserting a row would reassign every name after it.'
        )
        raise TemplateSyntaxError(msg)


def _reject_block_form(parser: Parser, token: Token) -> Node:
    """Claim the block grammar so slots fail explicitly rather than obscurely."""
    _ = parser, token
    msg = (
        f'Slots are not supported yet, so {{% {TAG_NAME} %}} is self-closing and '
        f'has no {{% {END_TAG_NAME} %}}. Slot content is authored in the parent '
        f'and rendered against the parent context, but a child that re-renders on '
        f'its own request has no parent render in flight; that is unresolved. '
        f'See design/components/spec.md §Deferred.'
    )
    raise TemplateSyntaxError(msg)


def register_component_tags(register: Any) -> None:
    register.tag(TAG_NAME, _parse_component_token)
    register.tag(END_TAG_NAME, _reject_block_form)
