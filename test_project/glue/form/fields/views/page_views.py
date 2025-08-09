from __future__ import annotations

from typing_extensions import TYPE_CHECKING

from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse

from django_spire.contrib.generic_views import portal_views

from test_project.glue.form.fields import forms, models


if TYPE_CHECKING:
    from django.core.handlers.wsgi import WSGIRequest


@permission_required('form.view_formfields')
def detail_view(request: WSGIRequest, pk: int) -> TemplateResponse:
    fields = get_object_or_404(models.Fields, pk=pk)

    context_data = {
        'fields': fields,
    }

    return portal_views.detail_view(
        request,
        obj=fields,
        context_data=context_data,
        template='fields/page/detail_page.html'
    )


@permission_required('form.view_formfields')
def list_view(request: WSGIRequest) -> TemplateResponse:
    context_data = {
        'fieldss': models.Fields.objects.all()
    }

    return portal_views.list_view(
        request,
        model=models.Fields,
        context_data=context_data,
        template='fields/page/list_page.html'
    )
