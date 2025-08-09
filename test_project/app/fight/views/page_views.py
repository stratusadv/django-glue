from __future__ import annotations

from typing_extensions import TYPE_CHECKING

from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse

from django_spire.contrib.generic_views import portal_views

from test_project.app.fight import forms, models


if TYPE_CHECKING:
    from django.core.handlers.wsgi import WSGIRequest


@permission_required('app.view_appfight')
def detail_view(request: WSGIRequest, pk: int) -> TemplateResponse:
    fight = get_object_or_404(models.Fight, pk=pk)

    context_data = {
        'fight': fight,
    }

    return portal_views.detail_view(
        request,
        obj=fight,
        context_data=context_data,
        template='fight/page/detail_page.html'
    )


@permission_required('app.view_appfight')
def list_view(request: WSGIRequest) -> TemplateResponse:
    context_data = {
        'fights': models.Fight.objects.all()
    }

    return portal_views.list_view(
        request,
        model=models.Fight,
        context_data=context_data,
        template='fight/page/list_page.html'
    )
