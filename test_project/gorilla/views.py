from django.http import HttpRequest
from django.shortcuts import render, get_object_or_404
from django.template.response import TemplateResponse

from django_glue import Glue
from test_project.gorilla.models import Gorilla, Skill
from test_project.gorilla.forms import GorillaForm


def list_view(request: HttpRequest):
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


def detail_view(request: HttpRequest, pk: int):
    gorilla = get_object_or_404(Gorilla, pk=pk)

    Glue.model(request=request, target=gorilla, unique_name='gorilla', access=Glue.Access.DELETE)

    return render(request, 'gorilla/page/detail_page.html')


def skills_view(request: HttpRequest):
    """Test page for ManyToMany fields - managing skills."""
    Glue.queryset(
        request=request, target=Skill.objects.all(), unique_name='skills', access=Glue.Access.DELETE
    )

    return render(request, 'gorilla/page/skills_page.html')


def detail_template_view(request: HttpRequest, pk: int):
    gorilla = get_object_or_404(Gorilla, pk=pk)

    Glue.model(request=request, target=gorilla, unique_name='gorilla', access=Glue.Access.DELETE)

    return TemplateResponse(request, 'gorilla/page/detail_page_partial.html')
