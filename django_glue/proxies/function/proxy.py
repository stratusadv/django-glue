from __future__ import annotations

import asyncio
import inspect

from django.http import HttpRequest

from django_glue.access.access import GlueAccess
from django_glue.proxies.function.contract import GlueFunctionProxyContractData
from django_glue.proxies.proxy import BaseGlueProxy
from django_glue.actions.decorators import action
from django_glue.resolver.action.schemas import ActionRequest
from django_glue.utils import get_attr_from_path_string


class GlueFunctionProxy(BaseGlueProxy):
    _subject_type = str
    _subject_type_name = 'Function'

    def __init__(
        self,
        function_path: str,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)

        self.function_path = function_path
        self.function = get_attr_from_path_string(function_path)

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
    def from_action_request(
        cls,
        action_request: ActionRequest,
        **kwargs,
    ) -> GlueFunctionProxy:
        contract_data = GlueFunctionProxyContractData(**action_request.contract.custom_data)

        return cls(
            function_path=contract_data.function_path,
            **kwargs,
        )

    @property
    def _custom_contract_data(self) -> dict:
        return {
            'function_path': self.function_path,
            'params': self._params,
        }

    @action(access=GlueAccess.VIEW)
    def execute(self, request: HttpRequest, action_kwargs: dict | None = None) -> dict:
        action_kwargs = action_kwargs or {}
        result = self.function(**action_kwargs)

        if asyncio.iscoroutine(result):
            result = asyncio.get_event_loop().run_until_complete(result)

        return {'result': result}
