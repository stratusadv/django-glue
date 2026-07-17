from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Callable, get_type_hints, TYPE_CHECKING

from django.http import HttpRequest

from django_glue.access import GlueAccess
from django_glue.exceptions import GlueRequestError
from django_glue.glue.attributes.base import BaseGlueAttribute

if TYPE_CHECKING:
    from django_glue.glue.base import BaseGlue


@dataclass
class PreparedAttributeCall:
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

    def __init__(self, *, owner: BaseGlue, name: str, access: GlueAccess) -> None:
        super().__init__(owner=owner, name=name, access=access)

    @property
    def metadata(self) -> dict[str, Any]:
        return {'namespace': 'callable'}

    def prepare(
        self,
        request_kwargs: dict[str, Any],
        context: dict[str, Any],
    ) -> PreparedAttributeCall:
        """
        Resolve kwargs and return a prepared call ready for execution.

        Inspects the callable's signature to inject context values (request, state,
        policy) by parameter name or type hint, then maps remaining client-provided
        kwargs to matching parameters.
        """
        target_callable = self.get()
        if not callable(target_callable):
            raise GlueRequestError(
                code='attribute_not_callable',
                message=f"Attribute '{self.name}' is not callable.",
                details={'attribute': self.name},
                status=422,
            )

        resolved_kwargs = self._resolve_call_kwargs(target_callable, request_kwargs, context)
        return PreparedAttributeCall(target=target_callable, kwargs=resolved_kwargs)

    def _resolve_call_kwargs(
        self,
        target: Callable[..., Any],
        request_kwargs: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Map context and request kwargs to the target callable's signature."""
        kwargs: dict[str, Any] = {}
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

        for param_name, param in signature.parameters.items():
            if param_name == 'self':
                continue
            if param_name in context:
                kwargs[param_name] = context[param_name]
                continue
            hint = type_hints.get(param_name)
            if hint is not None and isinstance(hint, type) and issubclass(hint, HttpRequest):
                kwargs[param_name] = context['request']
                continue
            if param_name in request_kwargs:
                kwargs[param_name] = request_kwargs[param_name]
                continue
            if param_name not in kwargs and param.default is inspect.Parameter.empty:
                continue

        if accepts_var_kwargs:
            for key, value in request_kwargs.items():
                kwargs.setdefault(key, value)

        return kwargs

    def call(self, kwargs: dict[str, Any], context: dict[str, Any]) -> Any:
        """Prepare and execute an attribute call."""
        return self.prepare(kwargs, context).execute()
