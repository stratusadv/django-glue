from __future__ import annotations

from typing_extensions import TYPE_CHECKING

from django.template.response import TemplateResponse

from django_spire.contrib import Breadcrumbs


if TYPE_CHECKING:
    from django.core.handlers.wsgi import WSGIRequest


def dashboard_view(request: WSGIRequest) -> TemplateResponse:
    crumbs = Breadcrumbs()
    crumbs.add_breadcrumb('Glue Forms')

    return TemplateResponse(
        request,
        context={},
        template='developer/form/page/dashboard_page.html'
    )

