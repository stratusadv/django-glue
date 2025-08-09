from __future__ import annotations
from typing import TYPE_CHECKING

from django_spire.contrib.service import BaseDjangoModelService
from test_project.app.training.services.factory_service import TrainingFactoryService
from test_project.app.training.services.processor_service import TrainingProcessorService
from test_project.app.training.services.intelligence_service import TrainingIntelligenceService


if TYPE_CHECKING:
    from test_project.app.training.models import Training


class TrainingService(BaseDjangoModelService['Training']):
    obj: Training

    intelligence = TrainingIntelligenceService()
    processor = TrainingProcessorService()
    factory = TrainingFactoryService()