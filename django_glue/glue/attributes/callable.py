from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Callable, get_type_hints, TYPE_CHECKING

from django.http import HttpRequest

from django_glue.access import GlueAccess
from django_glue.exceptions import GlueRequestError
from django_glue.glue.attributes.base import BaseGlueAttribute
from django_glue.glue.policy import GluePolicy
from django_glue.glue.schemas import AttributeCallResolverContext

if TYPE_CHECKING:
    from django_glue.glue.base import BaseGlue


@dataclass
class LoadedAttributeCall:
    """
    An attribute call with resolved target and kwargs, ready for execution.

    This object represents the final stage before invoking an attribute -
    the callable target and its arguments have been resolved and validated.
    Calling execute() performs the invocation.
    """

    target: Callable[..., Any]
    kwargs: dict[str, Any]

    def execute(self) -> Any:
        return self.target(**self.kwargs)


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
        access: GlueAccess,
        loads_state: bool = True,
        target: Any = None,
    ) -> None:
        super().__init__(owner=owner, name=name, access=access, target=target)
        self.loads_state = loads_state

    @property
    def metadata(self) -> dict[str, Any]:
        return {'namespace': 'callable'}

    def load_context(
        self,
        context: AttributeCallResolverContext,
    ) -> LoadedAttributeCall:
        """
        Resolve kwargs and return a prepared call ready for execution.

        Inspects the callable's signature to inject context values (request, state,
        policy) by parameter name or type hint, then maps remaining client-provided
        kwargs to matching parameters.
        """
        target_callable = self.get()
        if not callable(target_callable):
            # TODO: this is not the thing to raise
            raise GlueRequestError(
                code='attribute_not_callable',
                message=f"Attribute '{self.name}' is not callable.",
                details={'attribute': self.name},
                status=422,
            )

        resolved_kwargs = self._resolve_call_kwargs(
            target_callable,
            context
        )

        return LoadedAttributeCall(target=target_callable, kwargs=resolved_kwargs)

    def _resolve_call_kwargs(
        self,
        target: Callable[..., Any],
        context: AttributeCallResolverContext,
    ) -> dict[str, Any]:
        """Map context and request kwargs to the target callable's signature."""
        resolved_kwargs: dict[str, Any] = {}
        unwrapped = inspect.unwrap(target)
        signature = inspect.signature(unwrapped)
        function_globals = getattr(unwrapped, '__globals__', {})
        type_hints = get_type_hints(
            unwrapped,
            globalns={**function_globals, 'HttpRequest': HttpRequest},
        )
        accepts_var_kwargs = any(
            param.kind == inspect.Parameter.VAR_KEYWORD
            for param in signature.parameters.values()
        )

        call_kwargs = context.target_attribute_call_kwargs
        for param_name, param in signature.parameters.items():
            if param_name == 'self':
                continue
            if param_name in context.target_attribute_call_kwargs:
                resolved_kwargs[param_name] = call_kwargs[param_name]
                continue

            hint = type_hints.get(param_name)
            if hint is not None and isinstance(hint, type) and issubclass(hint, HttpRequest):
                resolved_kwargs[param_name] = context.request
                continue

            # Convention: a parameter named 'kwargs' receives the entire call_kwargs dict
            if param_name == 'kwargs':
                resolved_kwargs[param_name] = call_kwargs
                continue

            if param_name not in resolved_kwargs and param.default is inspect.Parameter.empty:
                continue

        if accepts_var_kwargs:
            for key, value in call_kwargs.items():
                resolved_kwargs.setdefault(key, value)

        return resolved_kwargs

    def call(self, context: AttributeCallResolverContext) -> Any:
        return self.load_context(context).execute()
