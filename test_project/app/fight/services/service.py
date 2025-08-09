from __future__ import annotations
from typing import TYPE_CHECKING

from django_spire.contrib.service import BaseDjangoModelService
from test_project.app.fight.services.factory_service import FightFactoryService
from test_project.app.fight.services.processor_service import FightProcessorService
from test_project.app.fight.services.intelligence_service import FightIntelligenceService


if TYPE_CHECKING:
    from test_project.app.fight.models import Fight


class FightService(BaseDjangoModelService['Fight']):
    obj: Fight

    intelligence = FightIntelligenceService()
    processor = FightProcessorService()
    factory = FightFactoryService()