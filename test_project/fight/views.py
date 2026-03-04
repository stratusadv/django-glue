from django.http import HttpRequest
from django.shortcuts import render

from django_glue import Glue
from test_project.fight.models import Fight
from test_project.fight.forms import FightForm, ContactPromoterForm
from test_project.gorilla.choices import FightStyleChoices
from test_project.gorilla.models import Gorilla


def list_view(request: HttpRequest):
    glue = Glue.request(request)

    glue.queryset(
        target=Fight.objects.all(),
        unique_name='fights',
        access=Glue.Access.DELETE,
        fields=[
            'name',
            'description',
            Glue.ForeignKeyField('red_corner', queryset=Gorilla.objects.filter(
                fight_style=FightStyleChoices.JUDO)),
            Glue.ForeignKeyField('blue_corner', queryset=Gorilla.objects.filter(
                fight_style=FightStyleChoices.WRESTLING)),
            'status',
            'location',
            'weather_conditions',
            'spectator_count',
            'terrain_type'
        ]
    )


    Glue.queryset(
        request=request,
        target=Fight.objects.all(),
        unique_name='fights',
        access=Glue.Access.DELETE,
        fields=[
            'name',
            'description',
            Glue.ForeignKeyField('red_corner', queryset=Gorilla.objects.filter(fight_style=FightStyleChoices.JUDO)),
            Glue.ForeignKeyField('blue_corner', queryset=Gorilla.objects.filter(fight_style=FightStyleChoices.WRESTLING)),
            'status',
            'location',
            'weather_conditions',
            'spectator_count',
            'terrain_type'
        ]
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
        access=Glue.Access.CHANGE,
    )

    Glue.form(
        request=request,
        unique_name='contact_form',
        target=ContactPromoterForm(),
        access=Glue.Access.CHANGE,
    )

    return render(request, 'fight/page/schedule_page.html')
