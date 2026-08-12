from __future__ import annotations

import json
from functools import cached_property
from typing import TYPE_CHECKING, Any, TypeAlias

from django_glue.access import GlueAccess
from django_glue.encoders import GlueResponseJSONEncoder
from django_glue.glue.base import BaseGlue
from django_glue.glue.loading import LoadingStrategy

if TYPE_CHECKING:
    from django_glue.glue.policy import GluePolicy

JsonValue: TypeAlias = None | bool | int | float | str | list['JsonValue'] | dict[str, 'JsonValue']


class JsonGlue(BaseGlue):
    namespace = 'json'

    def __init__(
        self,
        target: JsonValue,
        *,
        name: str,
        access: GlueAccess = GlueAccess.VIEW,
        loading_strategy: LoadingStrategy = LoadingStrategy.LAZY,
    ) -> None:
        super().__init__(name=name, access=access, loading_strategy=loading_strategy)
        self.target: JsonValue = self._normalize_json_value(target)

    def get_identity(self) -> dict[str, JsonValue]:
        return {'value': self.target}

    def get_metadata(self) -> dict[str, Any]:
        return {
            'type': self._type_name(self.target),
            'attributes': {},
        }

    @classmethod
    def _reconstruct_from_policy(cls, policy: GluePolicy) -> JsonGlue:
        return cls(
            policy.identity['value'],
            name=policy.name,
            access=policy.access,
        )

    @staticmethod
    def _normalize_json_value(value: JsonValue) -> JsonValue:
        return json.loads(json.dumps(value, cls=GlueResponseJSONEncoder))

    @staticmethod
    def _type_name(value: JsonValue) -> str:
        if isinstance(value, list):
            return 'array'
        if isinstance(value, dict):
            return 'object'
        if value is None:
            return 'null'
        if isinstance(value, bool):
            return 'boolean'
        if isinstance(value, (int, float)):
            return 'number'
        return 'string'
