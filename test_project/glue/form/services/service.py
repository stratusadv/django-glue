from __future__ import annotations
from typing import TYPE_CHECKING

from django_spire.contrib.service import BaseDjangoModelService
from test_project.glue.form.services.factory_service import FormFactoryService
from test_project.glue.form.services.processor_service import FormProcessorService
from test_project.glue.form.services.intelligence_service import FormIntelligenceService


if TYPE_CHECKING:
    from test_project.glue.form.models import Form


class FormService(BaseDjangoModelService['Form']):
    obj: Form

    intelligence = FormIntelligenceService()
    processor = FormProcessorService()
    factory = FormFactoryService()