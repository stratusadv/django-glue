from __future__ import annotations

from typing_extensions import TYPE_CHECKING

from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import reverse

from django_spire.core.redirect.safe_redirect import safe_redirect_url
from django_spire.core.shortcuts import get_object_or_null_obj
from django_spire.contrib.form.utils import show_form_errors
from django_spire.history.activity.utils import add_form_activity
from django_spire.contrib.generic_views import portal_views, modal_views

import django_glue as dg

from test_project.app.gorilla.capability import forms, models


if TYPE_CHECKING:
    from django.core.handlers.wsgi import WSGIRequest


@permission_required('gorilla.delete_gorillacapability')
def delete_form_modal_view(request: WSGIRequest, pk: int) -> TemplateResponse:
    capability = get_object_or_404(models.Capability, pk=pk)

    form_action = reverse(
        'gorilla:capability:delete_form_modal',
        kwargs={'pk': pk}
    )

    def add_activity() -> None:
        capability.add_activity(
            user=request.user,
            verb='deleted',
            device=request.device,
            information=f'{request.user.get_full_name()} deleted a capability on "{capability.gorilla}".'
        )

    fallback = reverse(
        'gorilla:detail',
        kwargs={'pk': capability.gorilla.pk}
    )

    return_url = safe_redirect_url(request, fallback=fallback)

    return modal_views.dispatch_modal_delete_form_content(
        request,
        obj=capability,
        form_action=form_action,
        activity_func=add_activity,
        return_url=return_url,
    )


@permission_required('gorilla.delete_gorillacapability')
def delete_view(request: WSGIRequest, pk: int) -> TemplateResponse:
    capability = get_object_or_404(models.Capability, pk=pk)

    return_url = request.GET.get(
        'return_url',
        reverse('capability:page:list')
    )

    return portal_views.delete_form_view(
        request,
        obj=capability,
        return_url=return_url
    )


@permission_required('gorilla.change_gorillacapability')
def form_content_modal_view(request: WSGIRequest, pk: int) -> TemplateResponse:
    capability = get_object_or_404(models.Capability, pk=pk)

    dg.glue_model_object(request, 'capability', capability)

    context_data = {
        'capability': capability
    }

    return TemplateResponse(
        request,
        context=context_data,
        template='capability/modal/content/form_modal_content.html'
    )


@permission_required('gorilla.change_gorillacapability')
def form_view(request: WSGIRequest, pk: int) -> TemplateResponse:
    capability = get_object_or_null_obj(models.Capability, pk=pk)

    dg.glue_model_object(request, 'capability', capability, 'view')

    if request.method == 'POST':
        form = forms.PlaceholderForm(request.POST, instance=capability)

        if form.is_valid():
            capability = form.save()
            add_form_activity(capability, pk, request.user)

            return redirect(
                request.GET.get(
                    'return_url',
                    reverse('capability:page:list')
                )
            )

        show_form_errors(request, form)
    else:
        form = forms.PlaceholderForm(instance=capability)

    return portal_views.form_view(
        request,
        form=form,
        obj=capability,
        template='capability/page/form_page.html'
    )
