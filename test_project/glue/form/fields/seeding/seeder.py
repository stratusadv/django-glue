from __future__ import annotations

from test_project.glue.form.fields import models

from django_spire.contrib.seeding import DjangoModelSeeder


class FieldsModelSeeder(DjangoModelSeeder):
     model_class = models.Fields
     fields = {

     }

