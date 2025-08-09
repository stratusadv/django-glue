from __future__ import annotations
from typing import TYPE_CHECKING

from django_spire.contrib.service import BaseDjangoModelService

if TYPE_CHECKING:
    from test_project.glue.form.models import Form


class FormIntelligenceService(BaseDjangoModelService['Form']):
    obj: Form
