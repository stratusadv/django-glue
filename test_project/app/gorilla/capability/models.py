from __future__ import annotations

from django.db import models
from django.urls import reverse
from django.utils.timezone import now

from django_spire.contrib.breadcrumb import Breadcrumbs
from django_spire.history.mixins import HistoryModelMixin

from test_project.app.gorilla.capability import querysets
from test_project.app.gorilla.capability.choices import CapabilityLevelChoices
from test_project.app.gorilla.models import Gorilla
from test_project.app.capability.models import Capability as MainCapability


class GorillaCapability(HistoryModelMixin):
    gorilla = models.ForeignKey(
        Gorilla,
        on_delete=models.CASCADE,
        related_name='capabilities',
        related_query_name='capability'
    )

    capability = models.ForeignKey(
        MainCapability,
        on_delete=models.CASCADE,
        related_name='gorilla_capabilities',
        related_query_name='gorilla_capability'
    )

    level = models.IntegerField(
        choices=CapabilityLevelChoices.choices,
        default=CapabilityLevelChoices.INTERMEDIATE
    )

    acquired_at = models.DateTimeField(default=now)

    objects = querysets.CapabilityQuerySet().as_manager()

    def __str__(self):
        return f"{self.gorilla.name}'s {self.capability.name} - Level {self.level}"

    @classmethod
    def base_breadcrumb(cls) -> Breadcrumbs:
        crumbs = Breadcrumbs()

        crumbs.add_breadcrumb(
            'Capability',
            reverse('gorilla:capability:page:list')
        )

        return crumbs

    def breadcrumbs(self) -> Breadcrumbs:
        crumbs = Breadcrumbs()
        crumbs.add_base_breadcrumb(self._meta.model)

        if self.pk:
            crumbs.add_breadcrumb(
                str(self),
                reverse(
                    'gorilla:capability:page:detail',
                    kwargs={'pk': self.pk}
                )
            )

        return crumbs

    class Meta:
        verbose_name = 'Gorilla Capability'
        verbose_name_plural = 'Gorilla Capabilities'
        db_table = 'gorilla_capability'
