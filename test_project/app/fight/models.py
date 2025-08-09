from __future__ import annotations

from django.db import models
from django.urls import reverse

from django_spire.contrib.breadcrumb import Breadcrumbs
from django_spire.history.mixins import HistoryModelMixin

from test_project.app.fight import querysets
from test_project.app.fight.choices import LocationChoices, WeatherConditionChoices, TerrainTypeChoices, FightStatusChoices


class Fight(HistoryModelMixin):
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
        related_name='winner',
        null=True,
        blank=True
    )

    loser = models.ForeignKey(
        'gorilla.Gorilla',
        on_delete=models.SET_NULL,
        related_name='loser',
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
        default=WeatherConditionChoices.ARCTIC_FREEZE
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

    date_time = models.DateTimeField(auto_now_add=True)

    objects = querysets.FightQuerySet().as_manager()

    def __str__(self):
        return self.name

    @classmethod
    def base_breadcrumb(cls) -> Breadcrumbs:
        crumbs = Breadcrumbs()

        crumbs.add_breadcrumb(
            'Fight',
            reverse('app:fight:page:list')
        )

        return crumbs

    def breadcrumbs(self) -> Breadcrumbs:
        crumbs = Breadcrumbs()
        crumbs.add_base_breadcrumb(self._meta.model)

        if self.pk:
            crumbs.add_breadcrumb(
                str(self),
                reverse(
                    'app:fight:page:detail',
                    kwargs={'pk': self.pk}
                )
            )

        return crumbs

    class Meta:
        verbose_name = 'Fight'
        verbose_name_plural = 'Fights'
        db_table = 'app_fight'
