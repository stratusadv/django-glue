from __future__ import annotations

from typing_extensions import TYPE_CHECKING

from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse

from django_spire.contrib.generic_views import portal_views

from test_project.app.training.capability import forms, models


if TYPE_CHECKING:
    from django.core.handlers.wsgi import WSGIRequest


@permission_required('training.view_trainingcapability')
def detail_view(request: WSGIRequest, pk: int) -> TemplateResponse:
    capability = get_object_or_404(models.Capability, pk=pk)

    context_data = {
        'capability': capability,
    }

    return portal_views.detail_view(
        request,
        obj=capability,
        context_data=context_data,
        template='capability/page/detail_page.html'
    )


@permission_required('training.view_trainingcapability')
def list_view(request: WSGIRequest) -> TemplateResponse:
    context_data = {
        'capabilitys': models.Capability.objects.all()
    }

    return portal_views.list_view(
        request,
        model=models.Capability,
        context_data=context_data,
        template='capability/page/list_page.html'
    )
