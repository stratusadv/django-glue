from __future__ import annotations

from typing import TYPE_CHECKING

from django.template import TemplateDoesNotExist, TemplateSyntaxError
from django.template.loader import render_to_string

from django_glue.access.access import GlueAccess
from django_glue.proxies.proxy import BaseGlueProxy
from django_glue.proxies.template.state import GlueTemplateProxyState
from django_glue.bound_attributes.decorators import Attribute
from django_glue.resolver.exceptions import GlueResolverError

if TYPE_CHECKING:
    from django.http import HttpRequest
    pass


class GlueTemplateProxy(BaseGlueProxy):
    """Proxy for a Django template. Provides server-side rendering."""

    _subject_type = str
    _state_class = GlueTemplateProxyState

    @classmethod
    def register_policy(
        cls,
        request: HttpRequest,
        target: str,
        name: str,
        access: GlueAccess = GlueAccess.VIEW,
        namespace: str = 'template',
        initial_context_data: dict | None = None,
    ) -> None:
        state = GlueTemplateProxyState(template_path=target, context_data=initial_context_data or {})
        proxy = cls(name=name, namespace=namespace, access=access, state=state)
        proxy._register_with_request(request)

    @property
    def _custom_policy_details(self) -> dict:
        return {
            'template_path': self.state.template_path,
            'initial_context_data': self.state.context_data,
        }

    @Attribute(access=GlueAccess.VIEW)
    def render_html(self, request: HttpRequest, **context_kwargs: dict) -> dict:
        context_kwargs = context_kwargs or {}
        merged_context = {**self.state.context_data, **context_kwargs}

        try:
            html = render_to_string(
                template_name=self.state.template_path,
                context=merged_context,
            )
        except TemplateDoesNotExist as e:
            raise GlueResolverError(
                response_error=f'Template not found: {self.state.template_path}',
                response_status=404,
            ) from e
        except TemplateSyntaxError as e:
            raise GlueResolverError(
                response_error=f'Template syntax error in {self.state.template_path}: {e!s}',
                response_status=500,
            ) from e

        return {'html': html}
