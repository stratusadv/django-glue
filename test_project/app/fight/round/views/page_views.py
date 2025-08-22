from __future__ import annotations

from typing_extensions import TYPE_CHECKING

from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse

from django_spire.contrib.generic_views import portal_views

from test_project.app.fight.round import forms, models


if TYPE_CHECKING:
    from django.core.handlers.wsgi import WSGIRequest


@permission_required('fight.view_fightround')
def detail_view(request: WSGIRequest, pk: int) -> TemplateResponse:
    round = get_object_or_404(models.Round, pk=pk)

    context_data = {
        'round': round,
    }

    return portal_views.detail_view(
        request,
        obj=round,
        context_data=context_data,
        template='round/page/detail_page.html'
    )


@permission_required('fight.view_fightround')
def list_view(request: WSGIRequest) -> TemplateResponse:
    context_data = {
        'rounds': models.Round.objects.all()
    }

    return portal_views.list_view(
        request,
        model=models.Round,
        context_data=context_data,
        template='round/page/list_page.html'
    )
