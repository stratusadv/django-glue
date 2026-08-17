from __future__ import annotations

import asyncio
import inspect
from functools import cached_property
from typing import TYPE_CHECKING, Any, Callable

from django_glue.access import GlueAccess
from django_glue.glue.attributes import DeclaredAttribute
from django_glue.glue.base import BaseGlue
from django_glue.glue.loading import LoadingStrategy
from django_glue.utils import get_attr_from_path_string

if TYPE_CHECKING:
    from django_glue.glue.policy import GluePolicy


class FunctionGlue(BaseGlue):
    namespace = 'function'

    def __init__(
        self,
        target: str | None = None,
        *,
        name: str,
        access: GlueAccess = GlueAccess.VIEW,
        loading_strategy: LoadingStrategy = LoadingStrategy.LAZY,
    ) -> None:
        super().__init__(name=name, access=access, loading_strategy=loading_strategy)
        self.target = target

    def get_identity(self) -> dict[str, Any]:
        function = get_attr_from_path_string(self.target)
        return {
            'function_path': self.target,
            'params': self._params_for(function),
        }

    def get_state(self) -> dict[str, Any]:
        return {'function_path': self.target}

    def get_metadata(self) -> dict[str, Any]:
        return {
            'params': self.identity.get('params', []),
            'attributes': {
                name: attribute.metadata
                for name, attribute in self.attributes.items()
            },
        }

    @classmethod
    def _reconstruct_from_policy(cls, policy: GluePolicy) -> FunctionGlue:
        return cls(
            policy.identity['function_path'],
            name=policy.name,
            access=policy.access,
        )

    @DeclaredAttribute(required_access=GlueAccess.VIEW)
    def execute(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        function = get_attr_from_path_string(self.target)
        result = function(**kwargs)
        if inspect.iscoroutine(result):
            result = asyncio.get_event_loop().run_until_complete(result)
        return {'result': result}

    @staticmethod
    def _params_for(function: Callable[..., Any]) -> list[dict[str, Any]]:
        sig = inspect.signature(function)
        return [
            {
                'name': param_name,
                'type': (
                    str(param.annotation)
                    if param.annotation != inspect.Parameter.empty
                    else None
                ),
            }
            for param_name, param in sig.parameters.items()
            if param.kind in (
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.KEYWORD_ONLY,
            )
        ]
