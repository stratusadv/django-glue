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

from test_project.glue.form import forms, models


if TYPE_CHECKING:
    from django.core.handlers.wsgi import WSGIRequest


@permission_required('glue.delete_glueform')
def delete_form_modal_view(request: WSGIRequest, pk: int) -> TemplateResponse:
    form = get_object_or_404(models.Form, pk=pk)

    form_action = reverse(
        'glue:form:delete_form_modal',
        kwargs={'pk': pk}
    )

    def add_activity() -> None:
        form.add_activity(
            user=request.user,
            verb='deleted',
            device=request.device,
            information=f'{request.user.get_full_name()} deleted a form on "{form.glue}".'
        )

    fallback = reverse(
        'glue:detail',
        kwargs={'pk': form.glue.pk}
    )

    return_url = safe_redirect_url(request, fallback=fallback)

    return modal_views.dispatch_modal_delete_form_content(
        request,
        obj=form,
        form_action=form_action,
        activity_func=add_activity,
        return_url=return_url,
    )


@permission_required('glue.delete_glueform')
def delete_view(request: WSGIRequest, pk: int) -> TemplateResponse:
    form = get_object_or_404(models.Form, pk=pk)

    return_url = request.GET.get(
        'return_url',
        reverse('form:page:list')
    )

    return portal_views.delete_form_view(
        request,
        obj=form,
        return_url=return_url
    )


@permission_required('glue.change_glueform')
def form_content_modal_view(request: WSGIRequest, pk: int) -> TemplateResponse:
    form = get_object_or_404(models.Form, pk=pk)

    dg.glue_model_object(request, 'form', form)

    context_data = {
        'form': form
    }

    return TemplateResponse(
        request,
        context=context_data,
        template='form/modal/content/form_modal_content.html'
    )


@permission_required('glue.change_glueform')
def form_view(request: WSGIRequest, pk: int) -> TemplateResponse:
    form = get_object_or_null_obj(models.Form, pk=pk)

    dg.glue_model_object(request, 'form', form, 'view')

    if request.method == 'POST':
        form = forms.PlaceholderForm(request.POST, instance=form)

        if form.is_valid():
            form = form.save()
            add_form_activity(form, pk, request.user)

            return redirect(
                request.GET.get(
                    'return_url',
                    reverse('form:page:list')
                )
            )

        show_form_errors(request, form)
    else:
        form = forms.PlaceholderForm(instance=form)

    return portal_views.form_view(
        request,
        form=form,
        obj=form,
        template='form/page/form_page.html'
    )
