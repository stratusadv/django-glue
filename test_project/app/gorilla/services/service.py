from __future__ import annotations
from typing import TYPE_CHECKING

from django_spire.contrib.service import BaseDjangoModelService
from test_project.app.gorilla.services.factory_service import GorillaFactoryService
from test_project.app.gorilla.services.processor_service import GorillaProcessorService
from test_project.app.gorilla.services.intelligence_service import GorillaIntelligenceService


if TYPE_CHECKING:
    from test_project.app.gorilla.models import Gorilla


class GorillaService(BaseDjangoModelService['Gorilla']):
    obj: Gorilla

    intelligence = GorillaIntelligenceService()
    processor = GorillaProcessorService()
    factory = GorillaFactoryService()