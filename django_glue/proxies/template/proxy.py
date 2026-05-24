from __future__ import annotations

from typing import TYPE_CHECKING

from django.template import TemplateDoesNotExist, TemplateSyntaxError, engines

from django_glue.access.access import GlueAccess
from django_glue.resolver.exceptions import GlueResolverError
from django_glue.proxies.proxy import BaseGlueProxy
from django_glue.proxies.decorators import action

if TYPE_CHECKING:
    from django_glue.resolver.action.schemas import ActionPayloadSchema


class GlueTemplateProxy(BaseGlueProxy):
    _subject_type = str
    _subject_type_name = 'Template'

    def __init__(
        self,
        target: str,
        context_data: dict | None = None,
        **kwargs,
    ) -> None:
        super().__init__(target=target, **kwargs)

        self.template_name = target
        self._context_data = context_data or {}

    @classmethod
    def from_action_request_data(
        cls,
        template_name: str,
        context_data: dict | None = None,
        **kwargs,
    ) -> GlueTemplateProxy:
        return cls(
            target=template_name,
            context_data=context_data,
            **kwargs,
        )

    def _build_context_data(self) -> dict:
        return {
            'template_name': self.template_name,
            'context_data': self._context_data,
        }

    def to_context_data(self) -> dict:
        actions_data = {
            action_name: dict(action_parameters)
            for action_name, (_, action_parameters, _) in self.actions.items()
        }

        return (
            {'actions': actions_data, 'subject_type': self._subject_type_name}
            | self._build_context_data()
        )

    @action(access=GlueAccess.VIEW)
    def render_html(self, action_data: ActionPayloadSchema) -> dict:
        post_data = action_data.post_data or {}
        merged_context = {**self._context_data, **post_data}

        try:
            django_engine = engines['django']
            template = django_engine.get_template(self.template_name)
            html = template.render(merged_context)
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
