from __future__ import annotations

from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.template.response import TemplateResponse
from django.urls import reverse

from django_glue import Glue
from test_project.gorilla.forms import GorillaGlueModelForm
from test_project.gorilla.models import Gorilla, Skill
from test_project.gorilla.forms import GorillaForm


def list_view(request: HttpRequest) -> HttpResponse:
    Glue.queryset(
        request=request,
        target=Gorilla.objects.order_by('-updated_at').all(),
        unique_name='gorillas',
        access=Glue.Access.DELETE,
    )

    Glue.form(
        request=request, target=GorillaForm(), unique_name='gorilla_form', access=Glue.Access.CHANGE
    )

    Glue.model(
        request=request, target=Gorilla(), unique_name='new_gorilla', access=Glue.Access.CHANGE
    )

    return render(request, 'gorilla/page/list_page.html')


def detail_view(request: HttpRequest, pk: int) -> HttpResponse:
    gorilla = get_object_or_404(Gorilla, pk=pk)

    Glue.model(request=request, target=gorilla, unique_name='gorilla', access=Glue.Access.DELETE)

    return render(request, 'gorilla/page/detail_page.html')


def skills_view(request: HttpRequest) -> HttpResponse:
    Glue.queryset(
        request=request, target=Skill.objects.all(), unique_name='skills', access=Glue.Access.DELETE
    )

    return render(request, 'gorilla/page/skills_page.html')


def detail_template_view(request: HttpRequest, pk: int) -> HttpResponse:
    gorilla = get_object_or_404(Gorilla, pk=pk)

    Glue.model(request=request, target=gorilla, unique_name='gorilla', access=Glue.Access.DELETE)

    return TemplateResponse(request, 'gorilla/page/detail_page_partial.html')


def progressive_form_view(request: HttpRequest) -> HttpResponse:
    Glue.form(
        request=request,
        target=GorillaGlueModelForm,
        unique_name='progressive_form',
        access=Glue.Access.CHANGE,
    )
    return TemplateResponse(request, 'gorilla/page/progressive_form_page.html')


def arena_view(request: HttpRequest, pk: int) -> HttpResponse:
    gorilla = get_object_or_404(Gorilla, pk=pk)

    Glue.model(request=request, target=gorilla, unique_name='gorilla', access=Glue.Access.CHANGE)

    Glue.template(
        request=request, target='gorilla/component/fighter_rank_card.html', unique_name='rank_card'
    )

    Glue.function(
        request=request,
        target='test_project.gorilla.utils.calculate_fighter_rank',
        unique_name='calculate_fighter_rank',
    )

    Glue.function(
        request=request,
        target='test_project.gorilla.utils.generate_introduction',
        unique_name='generate_introduction',
    )

    Glue.function(
        request=request,
        target='test_project.gorilla.utils.predict_fight_outcome',
        unique_name='predict_fight_outcome',
    )

    return render(request, 'gorilla/page/arena_page.html', context={'pk': pk})


def random_arena_view(request: HttpRequest) -> HttpResponseRedirect:
    gorilla = Gorilla.objects.order_by('?').first()
    if gorilla is None:
        return HttpResponseRedirect(reverse('gorilla:list'))
    return HttpResponseRedirect(reverse('gorilla:arena', args=[gorilla.pk]))
