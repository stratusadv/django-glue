from __future__ import annotations

import hmac
import json
from typing import TYPE_CHECKING, Any, Self

from django.conf import settings
from django.utils import timezone
from pydantic import BaseModel, Field, model_validator

from django_glue.access import GlueAccess
from django_glue.conf import settings as glue_settings

if TYPE_CHECKING:
    from django_glue.glue.base import BaseGlue


class GluePolicy(BaseModel):
    """Signed client-held policy for a glued backend object."""

    session_id: str
    request_user_id: Any
    name: str
    namespace: str
    identity: dict[str, Any]
    access: GlueAccess
    attributes: list[str | Self] = Field(default_factory=list)
    created_at: float
    original_signature: str

    @classmethod
    def from_glue_object(
        cls,
        *,
        glue_object: BaseGlue,
    ) -> Self:
        attributes: list[str | Self] = []

        for attr_name, attr in glue_object.attributes.items():
            nested_glue = getattr(attr, 'glue_object', None)
            if nested_glue is not None:
                # Attribute is a nested glue object - include its policy
                nested_glue.request = glue_object.request
                attributes.append(cls.from_glue_object(glue_object=nested_glue))
            else:
                # Simple attribute - just include the name
                attributes.append(attr_name)

        return cls.new_signed_policy({
            'session_id': glue_object.request.session.session_key,
            'request_user_id': getattr(getattr(glue_object.request, 'user', None), 'id', None),
            'name': glue_object.name,
            'namespace': glue_object.namespace,
            'identity': glue_object.identity,
            'access': glue_object.access,
            'attributes': attributes,
        })

    @classmethod
    def new_signed_policy(cls, data: dict) -> Self:
        instance = cls.model_validate({
            **data,
            'created_at': timezone.now().timestamp(),
            'original_signature': '',
        })
        instance.original_signature = cls._sign_data(
            instance.model_dump(exclude={'original_signature'}, exclude_none=True)
        )
        return instance

    @staticmethod
    def _sign_data(data: dict) -> str:
        return hmac.digest(
            settings.SECRET_KEY.encode(),
            json.dumps(data, default=str, sort_keys=True).encode(),
            'sha256',
        ).hex()

    @property
    def is_signed(self) -> bool:
        """True if this policy has been signed."""
        return bool(self.original_signature)

    @property
    def computed_signature(self) -> str:
        return self._sign_data(self.model_dump(exclude={'original_signature'}, exclude_none=True))

    def refresh_signature(self) -> Self:
        self.created_at = timezone.now().timestamp()
        self.original_signature = self._sign_data(
            self.model_dump(exclude={'original_signature'}, exclude_none=True)
        )
        return self

    @model_validator(mode='after')
    def validate_original_signature(self) -> Self:
        if not self.is_signed:
            return self

        if not hmac.compare_digest(self.computed_signature, self.original_signature):
            from django_glue.exceptions import GlueInvalidPolicyError  # noqa: PLC0415
            raise GlueInvalidPolicyError(self.name)

        return self

    @model_validator(mode='after')
    def validate_not_expired(self) -> Self:
        if not self.is_signed:
            return self

        expires_at = self.created_at + glue_settings.DJANGO_GLUE_PROXY_POLICY_MAX_AGE_SECONDS
        if timezone.now().timestamp() > expires_at:
            from django_glue.exceptions import GlueExpiredPolicyError  # noqa: PLC0415
            raise GlueExpiredPolicyError(self.name)

        return self
