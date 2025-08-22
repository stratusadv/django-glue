from __future__ import annotations

from test_project.app.training import models

from django_spire.contrib.seeding import DjangoModelSeeder


class TrainingModelSeeder(DjangoModelSeeder):
     model_class = models.Training
     fields = {

     }

