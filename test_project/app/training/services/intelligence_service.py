from __future__ import annotations
from typing import TYPE_CHECKING

from django_spire.contrib.service import BaseDjangoModelService

if TYPE_CHECKING:
    from test_project.app.training.models import Training


class TrainingIntelligenceService(BaseDjangoModelService['Training']):
    obj: Training
