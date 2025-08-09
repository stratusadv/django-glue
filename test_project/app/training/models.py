from __future__ import annotations

from django.db import models
from django.urls import reverse

from django_spire.contrib.breadcrumb import Breadcrumbs
from django_spire.history.mixins import HistoryModelMixin

from test_project.app.training import querysets
from test_project.app.gorilla.models import Gorilla
from test_project.app.capability.models import Capability


class Training(HistoryModelMixin):
    name = models.CharField(max_length=255)
    description = models.TextField(default='')
    gorilla = models.ForeignKey(Gorilla, on_delete=models.CASCADE, related_name='trainings')
    training_type = models.CharField(max_length=100, default='')
    duration_minutes = models.IntegerField(default=0)
    intensity_level = models.IntegerField(default=1)
    capability = models.ForeignKey(Capability, on_delete=models.CASCADE, related_name='trainings')
    capability_gain = models.IntegerField(default=0)
    training_date = models.DateField(auto_now_add=True)

    objects = querysets.TrainingQuerySet().as_manager()

    def __str__(self):
        return self.name

    @classmethod
    def base_breadcrumb(cls) -> Breadcrumbs:
        crumbs = Breadcrumbs()

        crumbs.add_breadcrumb(
            'Training',
            reverse('app:training:page:list')
        )

        return crumbs

    def breadcrumbs(self) -> Breadcrumbs:
        crumbs = Breadcrumbs()
        crumbs.add_base_breadcrumb(self._meta.model)

        if self.pk:
            crumbs.add_breadcrumb(
                str(self),
                reverse(
                    'app:training:page:detail',
                    kwargs={'pk': self.pk}
                )
            )

        return crumbs

    class Meta:
        verbose_name = 'Training'
        verbose_name_plural = 'Trainings'
        db_table = 'app_training'
