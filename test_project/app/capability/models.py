from __future__ import annotations

from django.db import models
from django.urls import reverse

from django_spire.contrib.breadcrumb import Breadcrumbs
from django_spire.history.mixins import HistoryModelMixin

from test_project.app.capability import querysets


class Capability(HistoryModelMixin):
    name = models.CharField(max_length=255)
    description = models.TextField(default='')
    type = models.CharField(max_length=100, default='')
    base_value = models.IntegerField(default=0)
    max_value = models.IntegerField(default=100)
    training_difficulty = models.IntegerField(default=1)
    is_attribute = models.BooleanField(default=False)
    is_skill = models.BooleanField(default=True)
    power_level = models.IntegerField(default=0)
    stamina_cost = models.IntegerField(default=0)
    cooldown = models.IntegerField(default=0)
    is_offensive = models.BooleanField(default=False)
    is_defensive = models.BooleanField(default=False)

    objects = querysets.CapabilityQuerySet().as_manager()

    def __str__(self):
        return self.name

    @classmethod
    def base_breadcrumb(cls) -> Breadcrumbs:
        crumbs = Breadcrumbs()

        crumbs.add_breadcrumb(
            'Capability',
            reverse('app:capability:page:list')
        )

        return crumbs

    def breadcrumbs(self) -> Breadcrumbs:
        crumbs = Breadcrumbs()
        crumbs.add_base_breadcrumb(self._meta.model)

        if self.pk:
            crumbs.add_breadcrumb(
                str(self),
                reverse(
                    'app:capability:page:detail',
                    kwargs={'pk': self.pk}
                )
            )

        return crumbs

    class Meta:
        verbose_name = 'Capability'
        verbose_name_plural = 'Capabilitys'
        db_table = 'app_capability'
