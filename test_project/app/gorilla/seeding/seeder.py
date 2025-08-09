from __future__ import annotations

from test_project.app.gorilla import models

from django_spire.contrib.seeding import DjangoModelSeeder


class GorillaModelSeeder(DjangoModelSeeder):
     model_class = models.Gorilla
     fields = {

     }

