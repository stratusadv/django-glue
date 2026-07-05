from __future__ import annotations

import json

from pydantic import BaseModel, field_validator
from django.core import signing

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from django_glue.actions import GlueAction
    from django_glue.access.access import GlueAccess


class GlueProxyContract(BaseModel):
    name: str
    actions: dict[str, GlueAction]
    namespace: str
    access: GlueAccess
    original_signature: str
    custom_data: dict

    @classmethod
    def initialize(cls, data: dict) -> GlueProxyContract:
        return cls.model_validate(**{
            'original_signature': cls._sign_data(data),
            **data
        })

    @staticmethod
    def _sign_data(data: dict) -> str:
        return signing.dumps(json.dumps(data, sort_keys=True).encode('utf-8'))

    @property
    def computed_signature(self) -> str:
        return self._sign_data(self.model_dump(exclude={'original_signature'}))

    @field_validator('original_signature', mode='after')
    def validate_original_signature(self, value: str) -> bool:
        return self.computed_signature == value

