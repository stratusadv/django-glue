from __future__ import annotations

from typing import TYPE_CHECKING

from django.template import TemplateDoesNotExist, TemplateSyntaxError
from django.template.loader import render_to_string

from django_glue.access.access import GlueAccess
from django_glue.resolver.exceptions import GlueResolverError
from django_glue.proxies.proxy import BaseGlueProxy
from django_glue.proxies.decorators import action

if TYPE_CHECKING:
    from django_glue.resolver.action.schemas import ActionRequest


class GlueTemplateProxy(BaseGlueProxy):
    _subject_type = str
    _subject_type_name = 'Template'

    def __init__(
        self,
        target: str,
        definition_context_data: dict | None = None,
        **kwargs,
    ) -> None:
        super().__init__(subject=target, **kwargs)

        self.template_name = target
        self._context_data = definition_context_data or {}

    @classmethod
    def from_action_request_data(
        cls,
        template_name: str,
        definition_context_data: dict | None = None,
        **kwargs
    ) -> GlueTemplateProxy:
        return cls(
            target=template_name,
            definition_context_data=definition_context_data,
            **kwargs,
        )

    def _custom_contract_data(self) -> dict:
        return {
            'template_name': self.template_name,
            'definition_context_data': self._context_data,
            'subject_type': self._subject_type_name
        }

    @action(access=GlueAccess.VIEW)
    def render_html(self, request, action_kwargs: dict = None) -> dict:
        action_kwargs = action_kwargs or {}
        merged_context = {**self._context_data, **action_kwargs}

        try:
            html = render_to_string(
                template_name=self.template_name,
                context=merged_context
            )
        except TemplateDoesNotExist as e:
            raise GlueResolverError(
                response_error=f'Template not found: {self.template_name}',
                response_status=404,
            ) from e
        except TemplateSyntaxError as e:
            raise GlueResolverError(
                response_error=f'Template syntax error in {self.template_name}: {e!s}',
                response_status=500,
            ) from e

        return {'html': html}
