from __future__ import annotations

import hashlib
import hmac
import json
from typing import Annotated

from pydantic import BaseModel, Field, model_validator
from django.conf import settings

from typing import Self, TYPE_CHECKING


if TYPE_CHECKING:
    from django_glue.proxies.proxy import BaseGlueProxy
    from django_glue.access.access import GlueAccess
    from django_glue.bound_attributes.attribute import BoundProxyAttribute

from django_glue.proxies.form.policy import GlueFormPolicyDetails
from django_glue.proxies.model.instance.policy import GlueModelInstancePolicyDetails
from django_glue.proxies.queryset.policy import GlueQuerySetPolicyDetails
from django_glue.proxies.template.policy import GlueTemplatePolicyDetails
from django_glue.proxies.function.policy import GlueFunctionPolicyDetails

ProxyPolicySubjectDetails = Annotated[
    GlueFormPolicyDetails | GlueModelInstancePolicyDetails | GlueQuerySetPolicyDetails | \
    GlueTemplatePolicyDetails | GlueFunctionPolicyDetails,
    Field(discriminator='namespace')
]


class ProxyPolicy(BaseModel):
    name: str
    bound_attributes: dict[str, BoundProxyAttribute]
    access: GlueAccess
    original_signature: str
    subject_details: ProxyPolicySubjectDetails

    @property
    def namespace(self) -> str:
        return self.subject_details.namespace

    @classmethod
    def new_signed_policy(cls, data: dict) -> ProxyPolicy:
        instance = cls.model_validate({**data, 'original_signature': ''})
        signature = cls._sign_data(instance.model_dump(exclude={'original_signature'}, exclude_none=True))
        instance.original_signature = signature
        return instance

    @staticmethod
    def _sign_data(data: dict) -> str:
        return hmac.digest(
            settings.SECRET_KEY.encode(),
            json.dumps(data, default=str, sort_keys=True).encode(),
            'sha256'
        ).hex()

    @property
    def computed_signature(self) -> str:
        return self._sign_data(self.model_dump(exclude={'original_signature'}, exclude_none=True))

    @model_validator(mode='after')
    def validate_original_signature(self) -> Self:
        if self.original_signature == '':
            return self
        if self.computed_signature != self.original_signature:
            from django_glue.exceptions import GlueInvalidPolicyError  # noqa: PLC0415
            raise GlueInvalidPolicyError(self.name)

        return self

    @property
    def proxy_class(self) -> type[BaseGlueProxy]:
        from django_glue.maps import ProxyType  # noqa: PLC0415
        return ProxyType.get_proxy_class(self.namespace)
