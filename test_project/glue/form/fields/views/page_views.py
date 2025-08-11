from __future__ import annotations

from typing_extensions import TYPE_CHECKING

from django.template.response import TemplateResponse

from django_spire.contrib import Breadcrumbs
from django_spire.contrib.generic_views import portal_views



if TYPE_CHECKING:
    from django.core.handlers.wsgi import WSGIRequest


def showcase_view(request: WSGIRequest) -> TemplateResponse:
    crumbs = Breadcrumbs()

    return portal_views.template_view(
        request,
        page_title='Form Fields',
        page_description='Showcase',
        breadcrumbs=crumbs,
        context_data={},
        template='glue/form/fields/page/showcase_page.html'
    )
