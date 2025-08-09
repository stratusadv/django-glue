from __future__ import annotations

from django.db import models
from django.urls import reverse

from django_spire.contrib.breadcrumb import Breadcrumbs
from django_spire.history.mixins import HistoryModelMixin

from test_project.app.training.capability import querysets


class Capability(HistoryModelMixin):
    name = models.CharField(max_length=255)
    description = models.TextField(default='')

    objects = querysets.CapabilityQuerySet().as_manager()

    def __str__(self):
        return self.name

    @classmethod
    def base_breadcrumb(cls) -> Breadcrumbs:
        crumbs = Breadcrumbs()

        crumbs.add_breadcrumb(
            'Capability',
            reverse('training:capability:page:list')
        )

        return crumbs

    def breadcrumbs(self) -> Breadcrumbs:
        crumbs = Breadcrumbs()
        crumbs.add_base_breadcrumb(self._meta.model)

        if self.pk:
            crumbs.add_breadcrumb(
                str(self),
                reverse(
                    'training:capability:page:detail',
                    kwargs={'pk': self.pk}
                )
            )

        return crumbs

    class Meta:
        verbose_name = 'Capability'
        verbose_name_plural = 'Capabilitys'
        db_table = 'training_capability'
