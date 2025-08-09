from __future__ import annotations

from test_project.app.capability import models

from django_spire.contrib.seeding import DjangoModelSeeder


class CapabilityModelSeeder(DjangoModelSeeder):
     model_class = models.Capability
     fields = {

     }

