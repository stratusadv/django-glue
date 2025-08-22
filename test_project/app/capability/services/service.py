from __future__ import annotations
from typing import TYPE_CHECKING

from django_spire.contrib.service import BaseDjangoModelService
from test_project.app.capability.services.factory_service import CapabilityFactoryService
from test_project.app.capability.services.processor_service import CapabilityProcessorService
from test_project.app.capability.services.intelligence_service import CapabilityIntelligenceService


if TYPE_CHECKING:
    from test_project.app.capability.models import Capability


class CapabilityService(BaseDjangoModelService['Capability']):
    obj: Capability

    intelligence = CapabilityIntelligenceService()
    processor = CapabilityProcessorService()
    factory = CapabilityFactoryService()