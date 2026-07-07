from __future__ import annotations

import hashlib
import hmac
import json

from pydantic import BaseModel, model_validator
from django.conf import settings

from typing import Self, TYPE_CHECKING


if TYPE_CHECKING:
    from django_glue.access.access import GlueAccess
    from django_glue.actions.action import GlueAction


class GlueProxyContract(BaseModel):
    name: str
    actions: dict[str, GlueAction]
    namespace: str
    access: GlueAccess
    subject_type: str
    original_signature: str
    custom_data: dict

    @classmethod
    def initialize(cls, data: dict) -> GlueProxyContract:
        signature = cls._sign_data(data)
        return cls.model_validate({**data, 'original_signature': signature})

    @staticmethod
    def _sign_data(data: dict) -> str:
        data_str = json.dumps(data, default=str, sort_keys=True)
        secret_key = settings.SECRET_KEY.encode()
        return hmac.new(secret_key, data_str.encode(), hashlib.sha256).hexdigest()

    @property
    def computed_signature(self) -> str:
        return self._sign_data(self.model_dump(exclude={'original_signature'}, exclude_none=True))

    @model_validator(mode='after')
    def validate_original_signature(self) -> Self:
        if self.computed_signature != self.original_signature:
            raise ValueError('Contract original signature does not match its computed signature! The data may have been tampered with!')

        return self

