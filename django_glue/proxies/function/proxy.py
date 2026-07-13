from __future__ import annotations

import asyncio
import inspect


from django_glue.access.access import GlueAccess
from django_glue.proxies.proxy import BaseGlueProxy
from django_glue.proxies.function.state import GlueFunctionProxyState
from django_glue.bound_attributes.decorators import Attribute
from django_glue.utils import get_attr_from_path_string
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.http import HttpRequest


class GlueFunctionProxy(BaseGlueProxy):
    """Proxy for a Python callable. Provides execution of arbitrary functions."""

    _subject_type = str
    _state_class = GlueFunctionProxyState

    @classmethod
    def register_policy(
        cls,
        request: HttpRequest,
        target: str,
        name: str,
        access: GlueAccess = GlueAccess.VIEW,
        namespace: str = 'function',
    ) -> None:
        function = get_attr_from_path_string(target)
        sig = inspect.signature(function)
        params = [
            {
                'name': param_name,
                'type': str(param.annotation) if param.annotation != inspect.Parameter.empty else None,
            }
            for param_name, param in sig.parameters.items()
            if param.kind in (
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.KEYWORD_ONLY,
            )
        ]
        state = GlueFunctionProxyState(function_path=target)
        proxy = cls(name=name, namespace=namespace, access=access, state=state)
        proxy._params = params
        proxy._function = function
        proxy._register_with_request(request)

    @property
    def _custom_policy_details(self) -> dict:
        return {
            'function_path': self.state.function_path,
            'params': getattr(self, '_params', []),
        }

    @Attribute(access=GlueAccess.VIEW)
    def execute(self, request: HttpRequest, **function_kwargs: dict) -> dict:
        function = get_attr_from_path_string(self.state.function_path)
        result = function(**function_kwargs)

        if asyncio.iscoroutine(result):
            result = asyncio.get_event_loop().run_until_complete(result)

        return {'result': result}
