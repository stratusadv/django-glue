from __future__ import annotations
from typing import TYPE_CHECKING

from django_spire.contrib.service import BaseDjangoModelService

if TYPE_CHECKING:
    from test_project.app.capability.models import Capability


class CapabilityProcessorService(BaseDjangoModelService['Capability']):
    obj: Capability
