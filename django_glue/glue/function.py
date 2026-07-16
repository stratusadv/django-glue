from __future__ import annotations

import inspect
from functools import cached_property
from typing import Any, Callable

from django.http import HttpRequest

from django_glue.access import GlueAccess
from django_glue.glue.attributes import Attribute
from django_glue.glue.base import BaseGlue
from django_glue.glue.metadata import GlueMetadata
from django_glue.glue.policy import GluePolicy
from django_glue.utils import get_attr_from_path_string


class FunctionGlue(BaseGlue):
    namespace = 'function'

    def __init__(
        self,
        target: str | None = None,
        *,
        request: HttpRequest,
        name: str,
        access: GlueAccess = GlueAccess.VIEW,
    ) -> None:
        super().__init__(request=request, name=name, access=access)
        self.target = target

    @property
    def identity(self) -> dict[str, Any]:
        function = get_attr_from_path_string(self.target)
        return {
            'function_path': self.target,
            'params': self._params_for(function),
        }

    @property
    def state(self) -> dict[str, Any]:
        return {'function_path': self.target}

    @cached_property
    def metadata(self) -> GlueMetadata:
        return GlueMetadata.from_payload({
            'namespace': self.namespace,
            'params': self.identity.get('params', []),
            'attributes': {
                name: attribute.metadata
                for name, attribute in self.attributes.items()
            },
        })

    @classmethod
    def from_policy(cls, policy: GluePolicy, request: HttpRequest) -> 'FunctionGlue':
        glue_object = cls(
            policy.identity['function_path'],
            request=request,
            name=policy.name,
            access=policy.access,
        )
        glue_object.policy = policy
        return glue_object

    @Attribute(access=GlueAccess.VIEW)
    def execute(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        function = get_attr_from_path_string(self.target)
        result = function(**kwargs)
        if inspect.iscoroutine(result):
            import asyncio
            result = asyncio.get_event_loop().run_until_complete(result)
        return {'result': result}

    @staticmethod
    def _params_for(function: Callable[..., Any]) -> list[dict[str, Any]]:
        sig = inspect.signature(function)
        return [
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
