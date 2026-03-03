from django.db import models
from django.utils import timezone

from test_project.fight.choices import (
    LocationChoices,
    WeatherConditionChoices,
    TerrainTypeChoices,
    FightStatusChoices,
)


class Fight(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(default='')

    red_corner = models.ForeignKey(
        'gorilla.Gorilla',
        on_delete=models.CASCADE,
        related_name='fights_as_red_corner'
    )

    blue_corner = models.ForeignKey(
        'gorilla.Gorilla',
        on_delete=models.CASCADE,
        related_name='fights_as_blue_corner'
    )

    winner = models.ForeignKey(
        'gorilla.Gorilla',
        on_delete=models.SET_NULL,
        related_name='fights_won',
        null=True,
        blank=True
    )

    loser = models.ForeignKey(
        'gorilla.Gorilla',
        on_delete=models.SET_NULL,
        related_name='fights_lost',
        null=True,
        blank=True
    )

    location = models.CharField(
        max_length=3,
        choices=LocationChoices.choices,
        default=LocationChoices.DINOSAUR_ISLAND
    )
    weather_conditions = models.CharField(
        max_length=3,
        choices=WeatherConditionChoices.choices,
        default=WeatherConditionChoices.PERFECT_BLUE_SKY
    )
    spectator_count = models.IntegerField(default=0)

    terrain_type = models.CharField(
        max_length=3,
        choices=TerrainTypeChoices.choices,
        default=TerrainTypeChoices.STEEL_DEATH_CAGE
    )
    status = models.CharField(
        max_length=3,
        choices=FightStatusChoices.choices,
        default=FightStatusChoices.SCHEDULED
    )

    date_time = models.DateTimeField(default=timezone.localtime)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Fight'
        verbose_name_plural = 'Fights'
        db_table = 'fight'
