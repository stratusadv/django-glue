from __future__ import annotations

import asyncio
import inspect
from typing import TYPE_CHECKING

from django_glue.access.access import GlueAccess
from django_glue.proxies.proxy import BaseGlueProxy
from django_glue.proxies.decorators import action
from django_glue.utils import get_class_from_path_string

if TYPE_CHECKING:
    from django_glue.resolver.action.schemas import ActionPayloadSchema


class GlueFunctionProxy(BaseGlueProxy):
    _subject_type = str
    _subject_type_name = 'Function'

    def __init__(
        self,
        target: str,
        **kwargs,
    ) -> None:
        super().__init__(target=target, **kwargs)

        self.function_path = target
        self.function = get_class_from_path_string(target)

        sig = inspect.signature(self.function)
        self._params = [
            {
                'name': name,
                'type': str(param.annotation) if param.annotation != inspect.Parameter.empty else None,
            }
            for name, param in sig.parameters.items()
            if param.kind in (
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.KEYWORD_ONLY,
            )
        ]

    @classmethod
    def from_action_request_data(
        cls,
        function_path: str,
        **kwargs,
    ) -> GlueFunctionProxy:
        return cls(
            target=function_path,
            **kwargs,
        )

    def _build_context_data(self) -> dict:
        return {
            'function_path': self.function_path,
            'params': self._params,
            'subject_type': self._subject_type_name
        }

    @action(access=GlueAccess.VIEW)
    def execute(self, request, user_data: dict = None) -> dict:
        user_data = user_data or {}
        result = self.function(**user_data)

        if asyncio.iscoroutine(result):
            result = asyncio.get_event_loop().run_until_complete(result)

        return {'result': result}
