from __future__ import annotations

from typing import TYPE_CHECKING

from django.http import HttpRequest
from django.template import TemplateDoesNotExist, TemplateSyntaxError
from django.template.loader import render_to_string

from django_glue.access.access import GlueAccess
from django_glue.proxies.template.contract import GlueTemplateProxyContractData
from django_glue.resolver.exceptions import GlueResolverError
from django_glue.proxies.proxy import BaseGlueProxy
from django_glue.actions.decorators import action

if TYPE_CHECKING:
    from django_glue.resolver.action.schemas import ActionRequest


class GlueTemplateProxy(BaseGlueProxy):
    _subject_type = str

    def __init__(
        self,
        template_path: str,
        initial_context_data: dict | None = None,
        namespace: str = 'template',
        **kwargs,
    ) -> None:
        super().__init__(namespace=namespace, **kwargs)

        self.template_path = template_path
        self.initial_context_data = initial_context_data or {}

    @classmethod
    def from_action_request(cls, action_request: ActionRequest) -> GlueTemplateProxy:
        contract_data = GlueTemplateProxyContractData(**action_request.contract.custom_data)

        return cls(
            name=action_request.contract.name,
            access=action_request.contract.access,
            template_path=contract_data.template_path,
            initial_context_data=contract_data.initial_context_data
        )

    @property
    def _custom_contract_data(self) -> dict:
        return {
            'template_path': self.template_path,
            'initial_context_data': self.template_path,
        }

    @action(access=GlueAccess.VIEW)
    def render_html(self, request: HttpRequest, **action_kwargs: dict) -> dict:
        action_kwargs = action_kwargs or {}
        merged_context = {**self.initial_context_data, **action_kwargs}

        try:
            html = render_to_string(
                template_name=self.template_path,
                context=merged_context
            )
        except TemplateDoesNotExist as e:
            raise GlueResolverError(
                response_error=f'Template not found: {self.template_path}',
                response_status=404,
            ) from e
        except TemplateSyntaxError as e:
            raise GlueResolverError(
                response_error=f'Template syntax error in {self.template_path}: {e!s}',
                response_status=500,
            ) from e

        return {'html': html}
