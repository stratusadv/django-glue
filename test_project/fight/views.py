from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from django_glue import Glue
from test_project.fight.forms import (
    ContactPromoterForm,
    FightForm,
    SearchableFighterChoiceForm,
)
from test_project.fight.models import Fight


def list_view(request: HttpRequest) -> HttpResponse:
    Glue.queryset(
        request=request,
        target=(
            Fight.objects
            .select_related(
                'red_corner',
                'blue_corner',
            )
            .all()
        ),
        unique_name='fights',
        access=Glue.Access.DELETE,
        fields=[
            'name',
            'description',
            'red_corner',
            'blue_corner',
            'status',
            'location',
            'weather_conditions',
            'spectator_count',
            'terrain_type',
        ],
        form=FightForm(),
    )

    relation_choice_form = SearchableFighterChoiceForm()
    initial_gorilla = relation_choice_form.fields['fighter'].queryset.first()
    if initial_gorilla is not None:
        relation_choice_form.initial['fighter'] = initial_gorilla.pk
    relation_choice_form.initial['fighters'] = list(
        relation_choice_form.fields['fighters'].queryset.values_list('pk', flat=True)[:2]
    )
    Glue.form(
        request=request,
        target=relation_choice_form,
        unique_name='relation_choice_form',
        access=Glue.Access.CHANGE,
    )

    return render(request, template_name='fight/page/list_page.html')


def schedule_view(request: HttpRequest) -> HttpResponse:
    """Form proxy demo - schedule a new fight and contact the promoter."""
    Glue.form(
        request=request,
        unique_name='fight_form',
        target=FightForm(),
        access=Glue.Access.CHANGE
    )

    Glue.form(
        request=request,
        unique_name='contact_form',
        target=ContactPromoterForm(),
        access=Glue.Access.CHANGE,
    )

    return render(request, 'fight/page/schedule_page.html')
