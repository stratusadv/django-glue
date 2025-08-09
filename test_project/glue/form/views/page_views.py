from __future__ import annotations

from typing_extensions import TYPE_CHECKING

from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse

from django_spire.contrib.generic_views import portal_views

from test_project.glue.form import forms, models


if TYPE_CHECKING:
    from django.core.handlers.wsgi import WSGIRequest


@permission_required('glue.view_glueform')
def detail_view(request: WSGIRequest, pk: int) -> TemplateResponse:
    form = get_object_or_404(models.Form, pk=pk)

    context_data = {
        'form': form,
    }

    return portal_views.detail_view(
        request,
        obj=form,
        context_data=context_data,
        template='form/page/detail_page.html'
    )


@permission_required('glue.view_glueform')
def list_view(request: WSGIRequest) -> TemplateResponse:
    context_data = {
        'forms': models.Form.objects.all()
    }

    return portal_views.list_view(
        request,
        model=models.Form,
        context_data=context_data,
        template='form/page/list_page.html'
    )
