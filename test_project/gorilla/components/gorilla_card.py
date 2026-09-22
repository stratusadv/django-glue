from __future__ import annotations

from django_glue import Glue
from test_project.gorilla.models import Gorilla


class GorillaCard(Glue.Component):
    """Exercises autodiscovery: nothing imports this module explicitly."""

    template = 'gorilla/component/gorilla_card.html'

    gorilla_id: int = Glue.attr(parameter=True)

    @Glue.property
    def name(self) -> str:
        return Gorilla.objects.values_list('name', flat=True).get(pk=self.gorilla_id)
