from __future__ import annotations

from typing_extensions import TYPE_CHECKING

from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse

from django_spire.contrib.generic_views import portal_views

from test_project.app.gorilla import forms, models


if TYPE_CHECKING:
    from django.core.handlers.wsgi import WSGIRequest


@permission_required('app.view_gorilla')
def detail_view(request: WSGIRequest, pk: int) -> TemplateResponse:
    gorilla = get_object_or_404(models.Gorilla, pk=pk)

    context_data = {
        'gorilla': gorilla,
    }

    return portal_views.detail_view(
        request,
        obj=gorilla,
        context_data=context_data,
        template='gorilla/page/detail_page.html'
    )


@permission_required('app.view_gorilla')
def list_view(request: WSGIRequest) -> TemplateResponse:
    context_data = {
        'gorillas': models.Gorilla.objects.all()
    }

    return portal_views.list_view(
        request,
        model=models.Gorilla,
        context_data=context_data,
        template='gorilla/page/list_page.html'
    )
