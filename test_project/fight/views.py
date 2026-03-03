import json

from django.http import HttpRequest
from django.shortcuts import render

from django_glue import Glue, GlueAccess
from test_project.fight.models import Fight
from test_project.fight.forms import FightForm, ContactPromoterForm
from test_project.gorilla.models import Gorilla


def list_view(request: HttpRequest):
    Glue.queryset(
        request=request,
        target=Fight.objects.all(),
        unique_name='fights',
        access=GlueAccess.DELETE,
        exclude=['date_time']
    )

    Glue.queryset(
        request=request,
        target=Gorilla.objects.all(),
        unique_name='gorilla_choices',
        access=GlueAccess.VIEW,
        fields=['id', 'name']
    )

    return render(
        request,
        template_name='fight/page/list_page.html'
    )


def schedule_view(request: HttpRequest):
    """Form proxy demo - schedule a new fight and contact the promoter."""
    Glue.form(
        request=request,
        unique_name='fight_form',
        target=FightForm(),
        access=GlueAccess.CHANGE,
    )

    Glue.form(
        request=request,
        unique_name='contact_form',
        target=ContactPromoterForm(),
        access=GlueAccess.CHANGE,
    )

    return render(request, 'fight/page/schedule_page.html')
