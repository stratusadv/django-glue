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
from django_glue.glue.attributes.definition import GlueAttributeKind

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


class GlueCallableCapability(BaseModel):
    allowed_arguments: tuple[str, ...] = ()


class GlueCapability(BaseModel):
    callables: dict[str, GlueCallableCapability] = Field(default_factory=dict)


class GluePolicy(BaseModel):
    """Signed client-held policy for a glued backend object."""

    session_id: str
    request_user_id: Any
    name: str
    namespace: str
    identity: dict[str, Any]
    access: GlueAccess
    attributes: list[str | Self] = Field(default_factory=list)
    address: str = ''
    children: dict[str, str] = Field(default_factory=dict)
    state_snapshot: dict[str, Any] = Field(default_factory=dict)
    capability: GlueCapability = Field(default_factory=GlueCapability)
    created_at: float
    token: str = ''

    TOKEN_SALT: ClassVar[str] = 'django_glue.glue.policy.GluePolicy'

    @classmethod
    def from_glue_object(
        cls,
        *,
        glue_object: BaseGlue,
    ) -> Self:
        attributes = [
            definition.path
            for definition in glue_object._attribute_registry
            if definition.kind in {
                GlueAttributeKind.VALUE,
                GlueAttributeKind.CALLABLE,
            }
        ]

        callables = {
            definition.path: {
                'allowed_arguments': definition.allowed_arguments,
            }
            for definition in glue_object._attribute_registry
            if definition.kind == GlueAttributeKind.CALLABLE
        }

        return cls.new_signed_policy({
            'session_id': glue_object.request.session.session_key,
            'request_user_id': getattr(getattr(glue_object.request, 'user', None), 'id', None),
            'name': glue_object.name,
            'namespace': glue_object.namespace,
            'identity': glue_object.identity,
            'access': glue_object.access,
            'attributes': attributes,
            'address': glue_object.address,
            'children': glue_object.children,
            'state_snapshot': glue_object._retained_state(),
            'capability': {
                'callables': callables,
            },
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
