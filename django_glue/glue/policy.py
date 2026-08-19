from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, ClassVar, Self

from django.conf import settings
from django.core import signing
from django.utils import timezone
from pydantic import BaseModel, Field, model_validator

from django_glue.access import GlueAccess
from django_glue.conf import settings as glue_settings
from django_glue.encoders import GlueResponseJSONEncoder

if TYPE_CHECKING:
    from django_glue.glue.base import BaseGlue


class GluePolicyTokenSerializer:
    """Serialize token payloads using the same type support as Glue responses."""

    def dumps(self, obj: Any) -> bytes:
        return json.dumps(
            obj,
            cls=GlueResponseJSONEncoder,
            separators=(',', ':'),
        ).encode('latin-1')

    def loads(self, data: bytes) -> Any:
        return json.loads(data.decode('latin-1'))


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
    token: str = ''

    TOKEN_SALT: ClassVar[str] = 'django_glue.glue.policy.GluePolicy'

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
                if hasattr(attr, '_prepare_glue_object'):
                    nested_glue = attr._prepare_glue_object()
                else:
                    nested_glue.request = glue_object.request
                attributes.append(cls.from_glue_object(glue_object=nested_glue))
            else:
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
        })
        instance.token = instance.to_token()
        return instance

    def to_token(self) -> str:
        """Return an opaque signed representation of this policy."""
        return signing.dumps(
            self.model_dump(exclude={'token'}),
            key=settings.SECRET_KEY,
            salt=self.TOKEN_SALT,
            serializer=GluePolicyTokenSerializer,
            # The Django client decodes this payload synchronously to construct
            # proxies, so keep it uncompressed and avoid browser decompression.
            compress=False,
        )

    @classmethod
    def from_token(cls, token: str) -> Self:
        """Verify and reconstruct a policy from its opaque token."""
        try:
            # Expiry is intentionally validated from the signed ``created_at`` field
            # below instead of with Django's ``max_age`` argument. ``max_age`` rejects
            # before returning the payload, which would prevent the resulting
            # GlueExpiredPolicyError from identifying the proxy by name.
            data = signing.loads(
                token,
                key=settings.SECRET_KEY,
                salt=cls.TOKEN_SALT,
                serializer=GluePolicyTokenSerializer,
            )
        except signing.BadSignature as exc:
            from django_glue.exceptions import GlueInvalidPolicyError  # noqa: PLC0415
            raise GlueInvalidPolicyError('policy') from exc

        return cls.model_validate({**data, 'token': token})

    @model_validator(mode='after')
    def validate_not_expired(self) -> Self:
        expires_at = self.created_at + glue_settings.DJANGO_GLUE_PROXY_POLICY_MAX_AGE_SECONDS
        if timezone.now().timestamp() > expires_at:
            from django_glue.exceptions import GlueExpiredPolicyError  # noqa: PLC0415
            raise GlueExpiredPolicyError(self.name)

        return self
