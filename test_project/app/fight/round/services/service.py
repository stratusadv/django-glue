from __future__ import annotations
from typing import TYPE_CHECKING

from django_spire.contrib.service import BaseDjangoModelService
from test_project.app.fight.round.services.factory_service import RoundFactoryService
from test_project.app.fight.round.services.processor_service import RoundProcessorService
from test_project.app.fight.round.services.intelligence_service import RoundIntelligenceService


if TYPE_CHECKING:
    from test_project.app.fight.round.models import Round


class RoundService(BaseDjangoModelService['Round']):
    obj: Round

    intelligence = RoundIntelligenceService()
    processor = RoundProcessorService()
    factory = RoundFactoryService()