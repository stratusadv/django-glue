from __future__ import annotations

from django.db import models
from django.urls import reverse

from django_spire.contrib.breadcrumb import Breadcrumbs
from django_spire.history.mixins import HistoryModelMixin

from test_project.app.fight import querysets
from test_project.app.gorilla.models import Gorilla


class Fight(HistoryModelMixin):
    name = models.CharField(max_length=255)
    description = models.TextField(default='')
    gorilla1 = models.ForeignKey(Gorilla, on_delete=models.CASCADE, related_name='fights_as_gorilla1')
    gorilla2 = models.ForeignKey(Gorilla, on_delete=models.CASCADE, related_name='fights_as_gorilla2')
    winner = models.ForeignKey(Gorilla, on_delete=models.SET_NULL, related_name='fights_won', null=True, blank=True)
    date_time = models.DateTimeField(auto_now_add=True)
    location = models.CharField(max_length=255, default='')
    weather_conditions = models.CharField(max_length=100, default='')
    terrain_type = models.CharField(max_length=100, default='')
    total_rounds = models.IntegerField(default=0)
    spectator_count = models.IntegerField(default=0)
    status = models.CharField(max_length=50, default='scheduled')

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
