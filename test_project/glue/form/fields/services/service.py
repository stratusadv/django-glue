from __future__ import annotations
from typing import TYPE_CHECKING

from django_spire.contrib.service import BaseDjangoModelService
from test_project.glue.form.fields.services.factory_service import FieldsFactoryService
from test_project.glue.form.fields.services.processor_service import FieldsProcessorService
from test_project.glue.form.fields.services.intelligence_service import FieldsIntelligenceService


if TYPE_CHECKING:
    from test_project.glue.form.fields.models import Fields


class FieldsService(BaseDjangoModelService['Fields']):
    obj: Fields

    intelligence = FieldsIntelligenceService()
    processor = FieldsProcessorService()
    factory = FieldsFactoryService()