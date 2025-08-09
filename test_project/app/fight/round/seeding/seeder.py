from __future__ import annotations

from test_project.app.fight.round import models

from django_spire.contrib.seeding import DjangoModelSeeder


class RoundModelSeeder(DjangoModelSeeder):
     model_class = models.Round
     fields = {

     }

