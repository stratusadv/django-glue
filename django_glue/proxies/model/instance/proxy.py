from __future__ import annotations

from typing import TYPE_CHECKING, Self, cast
from django.db.models import Model

from django_glue.proxies.form.state import GlueFormProxyState
from django_glue.proxies.model.instance.contract import GlueModelInstanceProxyContractData
from django_glue.proxies.model.proxy import BaseGlueModelProxy
from django_glue.utils import get_attr_from_path_string

if TYPE_CHECKING:
    from django_glue.resolver.action.schemas import ActionRequest


class GlueModelInstanceProxy(BaseGlueModelProxy):
    @classmethod
    def _from_action_request(cls, action_request: ActionRequest) -> Self:
        contract_data = GlueModelInstanceProxyContractData(**action_request.contract.custom_data)
        state_data = GlueFormProxyState(**action_request.contract.custom_data)

        return cls._from_deconstructed_action_request_data(
            name=action_request.contract.name,
            access=action_request.contract.access,
            model_class_path=contract_data.model_class_path,
            form_class_path=contract_data.form_class_path,
            allowed_fields=contract_data.allowed_fields,
            instance_pk=contract_data.target_pk,
            state=state_data
        )

    @property
    def _custom_contract_data(self) -> dict:
        return {
            'target_pk': self.model_instance.pk,
        } | super()._custom_contract_data
