from __future__ import annotations

from django.db import models
from django.urls import reverse

from django_spire.contrib.breadcrumb import Breadcrumbs
from django_spire.history.mixins import HistoryModelMixin

from test_project.app.fight.round import querysets
from test_project.app.fight.models import Fight


class FightRound(HistoryModelMixin):
    fight = models.ForeignKey(
        Fight,
        on_delete=models.CASCADE,
        related_name='rounds',
        related_query_name='round'
    )

    number = models.IntegerField(default=1)

    gorilla1_damage_dealt = models.IntegerField(default=0)
    gorilla2_damage_dealt = models.IntegerField(default=0)

    gorilla1_rank_points_earned = models.IntegerField(default=0)
    gorilla2_rank_points_earned = models.IntegerField(default=0)

    gorilla1_performance_rating = models.CharField(max_length=50, default='')
    gorilla2_performance_rating = models.CharField(max_length=50, default='')

    duration_seconds = models.IntegerField(default=0)

    objects = querysets.RoundQuerySet().as_manager()

    def __str__(self):
        return f"Round {self.number} of {self.fight.name}"

    @classmethod
    def base_breadcrumb(cls) -> Breadcrumbs:
        crumbs = Breadcrumbs()

        crumbs.add_breadcrumb(
            'Fight Round',
            reverse('fight:round:page:list')
        )

        return crumbs

    def breadcrumbs(self) -> Breadcrumbs:
        crumbs = Breadcrumbs()
        crumbs.add_base_breadcrumb(self._meta.model)

        if self.pk:
            crumbs.add_breadcrumb(
                str(self),
                reverse(
                    'fight:round:page:detail',
                    kwargs={'pk': self.pk}
                )
            )

        return crumbs

    class Meta:
        verbose_name = 'Fight Round'
        verbose_name_plural = 'Fight Rounds'
        db_table = 'fight_round'
