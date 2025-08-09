from __future__ import annotations

from django.db import models
from django.urls import reverse

from django_spire.contrib.breadcrumb import Breadcrumbs
from django_spire.history.mixins import HistoryModelMixin

from test_project.app.gorilla import querysets


class Gorilla(HistoryModelMixin):
    name = models.CharField(max_length=255)
    description = models.TextField(default='')
    age = models.IntegerField(default=0)
    weight = models.FloatField(default=0.0)
    height = models.FloatField(default=0.0)
    fight_style = models.CharField(max_length=100, default='')
    rank_points = models.IntegerField(default=0)
    rank_title = models.CharField(max_length=100, default='')
    rank_badge_image = models.CharField(max_length=255, blank=True, null=True)

    objects = querysets.GorillaQuerySet().as_manager()

    def __str__(self):
        return self.name

    @classmethod
    def base_breadcrumb(cls) -> Breadcrumbs:
        crumbs = Breadcrumbs()

        crumbs.add_breadcrumb(
            'Gorilla',
            reverse('app:gorilla:page:list')
        )

        return crumbs

    def breadcrumbs(self) -> Breadcrumbs:
        crumbs = Breadcrumbs()
        crumbs.add_base_breadcrumb(self._meta.model)

        if self.pk:
            crumbs.add_breadcrumb(
                str(self),
                reverse(
                    'app:gorilla:page:detail',
                    kwargs={'pk': self.pk}
                )
            )

        return crumbs

    class Meta:
        verbose_name = 'Gorilla'
        verbose_name_plural = 'Gorillas'
        db_table = 'gorilla'
