from __future__ import annotations

from functools import cached_property
from typing import Any

from django.template import TemplateDoesNotExist, TemplateSyntaxError
from django.template.loader import render_to_string

from django_glue.access import GlueAccess
from django_glue.glue.attributes import DeclaredAttribute
from django_glue.glue.base import BaseGlue
from django_glue.glue.metadata import GlueMetadata
from django_glue.glue.policy import GluePolicy
from django_glue.resolver.exceptions import GlueResolverError


class TemplateGlue(BaseGlue):
    namespace = 'template'

    def __init__(
        self,
        target: str | None = None,
        *,
        name: str,
        access: GlueAccess = GlueAccess.VIEW,
        initial_context_data: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(name=name, access=access)
        self.target = target
        self.initial_context_data = initial_context_data or {}

    @property
    def identity(self) -> dict[str, Any]:
        return {
            'template_path': self.target,
            'initial_context_data': self.initial_context_data,
        }

    @property
    def state(self) -> dict[str, Any]:
        return {
            'template_path': self.target,
            'context_data': self.initial_context_data,
        }

    @cached_property
    def metadata(self) -> GlueMetadata:
        return GlueMetadata.from_payload({
            'attributes': {
                name: attribute.metadata
                for name, attribute in self.attributes.items()
            },
        })

    @classmethod
    def _reconstruct_from_policy(cls, policy: GluePolicy) -> TemplateGlue:
        return cls(
            policy.identity['template_path'],
            name=policy.name,
            access=policy.access,
            initial_context_data=policy.identity.get('initial_context_data', {}),
        )

    @DeclaredAttribute(access=GlueAccess.VIEW)
    def render_html(self, kwargs: dict[str, Any]) -> dict[str, str]:
        context_data = self.initial_context_data
        merged_context = {**context_data, **kwargs}
        try:
            html = render_to_string(self.target, context=merged_context)
        except TemplateDoesNotExist as e:
            raise GlueResolverError(
                response_error=f'Template not found: {self.target}',
                response_status=404,
            ) from e
        except TemplateSyntaxError as e:
            raise GlueResolverError(
                response_error=f'Template syntax error in {self.target}: {e!s}',
                response_status=500,
            ) from e
        return {'html': html}
