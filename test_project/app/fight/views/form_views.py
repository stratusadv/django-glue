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

from test_project.app.fight import forms, models


if TYPE_CHECKING:
    from django.core.handlers.wsgi import WSGIRequest


@permission_required('app.delete_appfight')
def delete_form_modal_view(request: WSGIRequest, pk: int) -> TemplateResponse:
    fight = get_object_or_404(models.Fight, pk=pk)

    form_action = reverse(
        'app:fight:delete_form_modal',
        kwargs={'pk': pk}
    )

    def add_activity() -> None:
        fight.add_activity(
            user=request.user,
            verb='deleted',
            device=request.device,
            information=f'{request.user.get_full_name()} deleted a fight on "{fight.app}".'
        )

    fallback = reverse(
        'app:detail',
        kwargs={'pk': fight.app.pk}
    )

    return_url = safe_redirect_url(request, fallback=fallback)

    return modal_views.dispatch_modal_delete_form_content(
        request,
        obj=fight,
        form_action=form_action,
        activity_func=add_activity,
        return_url=return_url,
    )


@permission_required('app.delete_appfight')
def delete_view(request: WSGIRequest, pk: int) -> TemplateResponse:
    fight = get_object_or_404(models.Fight, pk=pk)

    return_url = request.GET.get(
        'return_url',
        reverse('fight:page:list')
    )

    return portal_views.delete_form_view(
        request,
        obj=fight,
        return_url=return_url
    )


@permission_required('app.change_appfight')
def form_content_modal_view(request: WSGIRequest, pk: int) -> TemplateResponse:
    fight = get_object_or_404(models.Fight, pk=pk)

    dg.glue_model_object(request, 'fight', fight)

    context_data = {
        'fight': fight
    }

    return TemplateResponse(
        request,
        context=context_data,
        template='fight/modal/content/form_modal_content.html'
    )


@permission_required('app.change_appfight')
def form_view(request: WSGIRequest, pk: int) -> TemplateResponse:
    fight = get_object_or_null_obj(models.Fight, pk=pk)

    dg.glue_model_object(request, 'fight', fight, 'view')

    if request.method == 'POST':
        form = forms.PlaceholderForm(request.POST, instance=fight)

        if form.is_valid():
            fight = form.save()
            add_form_activity(fight, pk, request.user)

            return redirect(
                request.GET.get(
                    'return_url',
                    reverse('fight:page:list')
                )
            )

        show_form_errors(request, form)
    else:
        form = forms.PlaceholderForm(instance=fight)

    return portal_views.form_view(
        request,
        form=form,
        obj=fight,
        template='fight/page/form_page.html'
    )
