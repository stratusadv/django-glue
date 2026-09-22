from __future__ import annotations

from django_glue import Glue


class FighterCard(Glue.Component):
    """Exercises recursive autodiscovery: nested a package deeper than components/."""

    template = 'gorilla/component/fighter_card.html'

    fighter_id: int = Glue.attr(parameter=True)
