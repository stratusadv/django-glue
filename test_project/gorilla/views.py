from django.http import HttpRequest
from django.shortcuts import render, get_object_or_404

from django_glue import Glue, GlueAccess
from test_project.gorilla.models import Gorilla, Skill
from test_project.gorilla.forms import GorillaForm


def list_view(request: HttpRequest):
    Glue.queryset(
        request=request,
        target=Gorilla.objects.order_by('-updated_at').all(),
        unique_name='gorillas',
        access=GlueAccess.DELETE,
    )

    Glue.form(
        request=request,
        target=GorillaForm(),
        unique_name='gorilla_form',
        access=GlueAccess.CHANGE,
    )

    Glue.model(
        request=request,
        target=Gorilla(),
        unique_name='new_gorilla',
        access=GlueAccess.CHANGE,
    )

    return render(request, 'gorilla/page/list_page.html')


def detail_view(request: HttpRequest, pk: int):
    gorilla = get_object_or_404(Gorilla, pk=pk)

    Glue.model(
        request=request,
        target=gorilla,
        unique_name='gorilla',
        access=GlueAccess.DELETE,
    )

    return render(request, 'gorilla/page/detail_page.html')


def skills_view(request: HttpRequest):
    """Test page for ManyToMany fields - managing skills."""
    Glue.queryset(
        request=request,
        target=Skill.objects.all(),
        unique_name='skills',
        access=GlueAccess.DELETE,
    )

    return render(request, 'gorilla/page/skills_page.html')
