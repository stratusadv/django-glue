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
        }

    def to_context_data(self) -> dict:
        actions_data = {
            action_name: dict(action_parameters)
            for action_name, (_, action_parameters, _) in self.actions.items()
        }

        return (
            {'actions': actions_data, 'subject_type': self._subject_type_name}
            | self._build_context_data()
        )

    @action(access=GlueAccess.VIEW)
    def execute(self, action_data: ActionPayloadSchema) -> dict:
        post_data = action_data.post_data or {}
        result = self.function(**post_data)

        if asyncio.iscoroutine(result):
            result = asyncio.get_event_loop().run_until_complete(result)

        return {'result': result}
