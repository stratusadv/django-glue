from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django_glue.access import GlueAccess
from django_glue.glue.attributes import DeclaredAttribute
from django_glue.glue.base import BaseGlue
from django_glue.glue.loading import LoadingStrategy
from django_glue.response import GlueResponse, GlueTemplateResponse

if TYPE_CHECKING:
    from django.http import HttpRequest


class Component(BaseGlue):
    template: str | None = None

    def __init__(
        self,
        *,
        name: str | None = None,
        template: str | None = None,
        access: GlueAccess = GlueAccess.VIEW,
        loading_strategy: LoadingStrategy = LoadingStrategy.EAGER,
    ) -> None:
        super().__init__(
            name=name,
            access=access,
            loading_strategy=loading_strategy,
        )

        resolved_template = template if template is not None else self.template
        if not resolved_template:
            msg = f'{type(self).__name__} must declare a template path.'
            raise ValueError(msg)

        self.template = resolved_template

    def get_context_data(self) -> dict[str, Any]:
        return {'component': self}

    @DeclaredAttribute(required_access=GlueAccess.VIEW)
    def render(self) -> GlueResponse:
        if self.request is None:
            msg = f"Cannot render unbound component '{self.name}'."
            raise RuntimeError(msg)

        request: HttpRequest = self.request
        return GlueTemplateResponse(
            request=request,
            template=self.template,
            context=self.get_context_data(),
        )
