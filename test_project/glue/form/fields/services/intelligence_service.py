from __future__ import annotations
from typing import TYPE_CHECKING

from django_spire.contrib.service import BaseDjangoModelService

if TYPE_CHECKING:
    from test_project.glue.form.fields.models import Fields


class FieldsIntelligenceService(BaseDjangoModelService['Fields']):
    obj: Fields
