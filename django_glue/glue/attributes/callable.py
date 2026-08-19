from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Callable, get_type_hints, TYPE_CHECKING

from django.http import HttpRequest

from django_glue.access import GlueAccess
from django_glue.glue.attributes.base import BaseGlueAttribute
from django_glue.resolver.attribute_call.context import AttributeCallRequestContext

if TYPE_CHECKING:
    from django_glue.glue.base import BaseGlue


@dataclass
class LoadedAttributeCall:
    """
    An attribute call with resolved target and parameters, ready for execution.

    This object represents the final stage before invoking an attribute -
    the callable target and its arguments have been resolved and validated.
    Calling execute() performs the invocation.
    """

    attr_owner_instance: Callable[..., Any]
    parameters: dict[str, Any]

    def execute(self) -> Any:
        return self.attr_owner_instance(**self.parameters)


class CallableAttribute(BaseGlueAttribute):
    """
    An attribute that can be invoked with arguments.

    Callable attributes wrap methods or functions that have been marked
    with @Attribute on the GlueObject or its subjects.
    """

    def __init__(
        self,
        *,
        owner: BaseGlue,
        name: str,
        required_access: GlueAccess,
        takes_client_state: bool | list[str] | tuple[str, ...] = True,
        updates_client_state: bool = True,
        render_as_html: bool = False,
        attr_owner_instance: Any = None,
    ) -> None:
        super().__init__(
            owner=owner,
            name=name,
            required_access=required_access,
            attr_owner_instance=attr_owner_instance
        )
        self.takes_client_state = takes_client_state
        self.updates_client_state = updates_client_state
        self.render_as_html = render_as_html

    @property
    def metadata(self) -> dict[str, Any]:
        return {
            'namespace': 'callable',
            'takes_client_state': self.takes_client_state,
        }

    def load_context(
        self,
        context: AttributeCallRequestContext,
    ) -> LoadedAttributeCall:
        """
        Resolve kwargs and return a prepared call ready for execution.

        Inspects the callable's signature to inject context values (request, state,
        policy) by parameter name or type hint, then maps remaining client-provided
        kwargs to matching parameters.
        """
        target_callable = self.get()
        if not callable(target_callable):
            msg = (
                f"CallableAttribute '{self.name}' resolved to a non-callable value. "
                f"This indicates a bug in attribute collection or the underlying target was modified."
            )
            raise TypeError(msg)

        resolved_parameters = self._resolve_call_parameters(
            target_callable,
            context
        )

        return LoadedAttributeCall(
            attr_owner_instance=target_callable, 
            parameters=resolved_parameters
        )

    def _resolve_call_parameters(
        self,
        target_callable: Callable[..., Any],
        context: AttributeCallRequestContext,
    ) -> dict[str, Any]:
        """Map context and request kwargs to the target callable's signature."""
        unwrapped_callable = inspect.unwrap(target_callable)
        signature = inspect.signature(unwrapped_callable)
        type_hints = self._get_type_hints(unwrapped_callable)

        resolved_parameters: dict[str, Any] = {}

        for param_name, param in signature.parameters.items():
            if param_name == 'self':
                continue

            resolved_param_value = self._resolve_call_parameter(
                param_name, param, type_hints.get(param_name), context
            )

            if resolved_param_value is not None:
                resolved_parameters[param_name] = resolved_param_value

        if self._accepts_variadic_parameters(signature):
            self._apply_variadic_parameters(
                context.target_attribute_call_kwargs,
                resolved_parameters
            )

        return resolved_parameters

    def _get_type_hints(self, func: Callable[..., Any]) -> dict[str, Any]:
        """Get type hints for a function, with HttpRequest available in the namespace."""
        function_globals = getattr(func, '__globals__', {})
        return get_type_hints(
            func,
            globalns={**function_globals, 'HttpRequest': HttpRequest},
        )

    def _resolve_call_parameter(
        self,
        param_name: str,
        param: inspect.Parameter,
        type_hint: type | None,
        context: AttributeCallRequestContext,
    ) -> Any | None:
        """
        Resolve a single parameter value.

        Returns the resolved value, or None if the parameter has a default.
        Raises ValueError if a required parameter cannot be resolved.
        """
        if param_name == 'self':
            return None

        call_parameters = context.target_attribute_call_kwargs

        # Client-provided value takes priority
        if param_name in call_parameters:
            return call_parameters[param_name]

        # Inject HttpRequest by type hint
        if (
            type_hint is not None and
            isinstance(type_hint, type) and
            issubclass(type_hint, HttpRequest)
        ):
            return context.request

        # Parameter has a default - let Python handle it
        if param.default is not inspect.Parameter.empty:
            return None

        # Required parameter with no resolution strategy
        msg = (
            f"Attribute '{self.name}' missing required argument: '{param_name}'. "
            f"Provided: {list(call_parameters.keys())}"
        )
        raise ValueError(msg)

    @staticmethod
    def _accepts_variadic_parameters(signature: inspect.Signature) -> bool:
        """Check if the signature accepts **kwargs."""
        return any(
            param.kind == inspect.Parameter.VAR_KEYWORD
            for param in signature.parameters.values()
        )

    @staticmethod
    def _apply_variadic_parameters(
        call_parameters: dict[str, Any],
        resolved_parameters: dict[str, Any],
    ) -> None:
        """Pass through any call parameters not already resolved."""
        for key, value in call_parameters.items():
            resolved_parameters.setdefault(key, value)

    def call(self, context: AttributeCallRequestContext) -> Any:
        return self.load_context(context).execute()
