from __future__ import annotations

from test_project.app.fight import models

from django_spire.contrib.seeding import DjangoModelSeeder


class FightModelSeeder(DjangoModelSeeder):
     model_class = models.Fight
     fields = {

     }

