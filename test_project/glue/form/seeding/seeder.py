from __future__ import annotations

from test_project.glue.form import models

from django_spire.contrib.seeding import DjangoModelSeeder


class FormModelSeeder(DjangoModelSeeder):
     model_class = models.Form
     fields = {

     }

