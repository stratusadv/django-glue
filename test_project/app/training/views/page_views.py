from __future__ import annotations

from typing_extensions import TYPE_CHECKING

from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse

from django_spire.contrib.generic_views import portal_views

from test_project.app.training import forms, models


if TYPE_CHECKING:
    from django.core.handlers.wsgi import WSGIRequest


@permission_required('app.view_apptraining')
def detail_view(request: WSGIRequest, pk: int) -> TemplateResponse:
    training = get_object_or_404(models.Training, pk=pk)

    context_data = {
        'training': training,
    }

    return portal_views.detail_view(
        request,
        obj=training,
        context_data=context_data,
        template='training/page/detail_page.html'
    )


@permission_required('app.view_apptraining')
def list_view(request: WSGIRequest) -> TemplateResponse:
    context_data = {
        'trainings': models.Training.objects.all()
    }

    return portal_views.list_view(
        request,
        model=models.Training,
        context_data=context_data,
        template='training/page/list_page.html'
    )
