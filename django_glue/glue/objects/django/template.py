from __future__ import annotations

from functools import cached_property
from typing import TYPE_CHECKING, Any

from django.template import TemplateDoesNotExist, TemplateSyntaxError
from django.template.loader import render_to_string

from django_glue.access import GlueAccess
from django_glue.glue.attributes import DeclaredAttribute
from django_glue.glue.base import BaseGlue
from django_glue.glue.loading import LoadingStrategy
from django_glue.exceptions import GlueRequestError

if TYPE_CHECKING:
    from django_glue.glue.policy import GluePolicy


class TemplateGlue(BaseGlue):
    namespace = 'template'

    def __init__(
        self,
        target: str | None = None,
        *,
        name: str,
        access: GlueAccess = GlueAccess.VIEW,
        initial_context_data: dict[str, Any] | None = None,
        loading_strategy: LoadingStrategy = LoadingStrategy.LAZY,
    ) -> None:
        super().__init__(name=name, access=access, loading_strategy=loading_strategy)
        self.target = target
        self.initial_context_data = initial_context_data or {}

    def get_identity(self) -> dict[str, Any]:
        return {
            'template_path': self.target,
            'initial_context_data': self.initial_context_data,
        }

    def get_state(self) -> dict[str, Any]:
        return {
            'context_data': self.initial_context_data,
        }

    def get_metadata(self) -> dict[str, Any]:
        return {
            'attributes': {
                name: attribute.metadata
                for name, attribute in self.attributes.items()
            },
        }

    @classmethod
    def _reconstruct_from_policy(cls, policy: GluePolicy) -> TemplateGlue:
        return cls(
            policy.identity['template_path'],
            name=policy.name,
            access=policy.access,
            initial_context_data=policy.identity.get('initial_context_data', {}),
        )

    @DeclaredAttribute(required_access=GlueAccess.VIEW)
    def render_html(self, kwargs: dict[str, Any]) -> dict[str, str]:
        context_data = self.initial_context_data
        merged_context = {**context_data, **kwargs}
        try:
            html = render_to_string(self.target, context=merged_context)
        except TemplateDoesNotExist as e:
            raise GlueRequestError(
                code='template_not_found',
                message=f'Template not found: {self.target}',
                status=404,
            ) from e
        except TemplateSyntaxError as e:
            raise GlueRequestError(
                code='template_syntax_error',
                message=f'Template syntax error in {self.target}: {e!s}',
                status=500,
            ) from e
        return {'html': html}
