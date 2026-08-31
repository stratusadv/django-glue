from __future__ import annotations

import os

import pytest

from django.contrib.auth import get_user_model

# pytest-playwright drives Django's live_server test-DB setup from inside its own asyncio event
# loop; without this, Django's SynchronousOnlyOperation guard trips on session-scoped DB setup.
os.environ.setdefault('DJANGO_ALLOW_ASYNC_UNSAFE', 'true')

from limelight.django import DjangoApplication

from test_project.fight.choices import (
    FightStatusChoices,
    LocationChoices,
    TerrainTypeChoices,
    WeatherConditionChoices,
)
from test_project.fight.models import Fight
from test_project.gorilla.models import Gorilla, Skill


@pytest.fixture
def gorilla_app_user(transactional_db):
    del transactional_db

    return get_user_model().objects.create_superuser(username='limelight')


@pytest.fixture
def application(live_server, gorilla_app_user):
    return DjangoApplication(live_server=live_server, user=gorilla_app_user)


@pytest.fixture
def seeded_gorillas(transactional_db):
    del transactional_db

    Fight.objects.all().delete()
    Skill.objects.all().delete()
    Gorilla.objects.all().delete()

    chest_pound = Skill.objects.create(
        name='Chest Pound',
        description='A confident display.',
        difficulty=2,
        level=30,
    )
    jungle_roar = Skill.objects.create(
        name='Jungle Roar',
        description='A room-shaking roar.',
        difficulty=5,
        level=45,
    )

    alpha = Gorilla.objects.create(
        name='Alpha Atlas',
        description='Steady leader of the troop.',
        age=12,
        weight=210.5,
        height=1.8,
        rank_points=700,
    )
    alpha.skills.set([chest_pound, jungle_roar])

    beta = Gorilla.objects.create(
        name='Beta Boulder',
        description='Heavy hitter with careful footwork.',
        age=24,
        weight=315.0,
        height=1.65,
        rank_points=300,
    )
    beta.skills.set([chest_pound])

    gamma = Gorilla.objects.create(
        name='Gamma Grove',
        description='Fast climber from the canopy.',
        age=8,
        weight=155.5,
        height=1.4,
        rank_points=950,
    )

    Fight.objects.create(
        name='Alpha vs Beta',
        description='A deterministic e2e fight.',
        red_corner=alpha,
        blue_corner=beta,
        location=LocationChoices.THUNDERDOME,
        weather_conditions=WeatherConditionChoices.OMINOUS_CLOUDS,
        terrain_type=TerrainTypeChoices.LAVA_FLOOR,
        status=FightStatusChoices.IN_PROGRESS,
        spectator_count=1234,
    )

    Fight.objects.create(
        name='Gamma Exhibition',
        description='A second fight for filtering.',
        red_corner=gamma,
        blue_corner=alpha,
        location=LocationChoices.COLOSSEUM,
        weather_conditions=WeatherConditionChoices.PERFECT_BLUE_SKY,
        terrain_type=TerrainTypeChoices.STEEL_DEATH_CAGE,
        status=FightStatusChoices.SCHEDULED,
        spectator_count=50,
    )

    return {'alpha': alpha, 'beta': beta, 'gamma': gamma}
