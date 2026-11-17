"""
Components sized by their parameters, for measuring what components cost: the
speed page renders and calls them in process, and the stress page mounts them
for the metrics panel to watch.
"""
from django_glue import Glue


class CardComponent(Glue.Component):
    template = 'lab/component/card.html'

    start: int = Glue.attr(0, parameter=True)
    count: int = Glue.attr(0)
    counted = Glue.event()

    @Glue.attr
    def increment(self) -> int:
        self.count += 1
        self.counted(value=self.count)
        return self.count


class DeckComponent(Glue.Component):
    """A parent whose cards are spawned from its size, so a call can add and drop children."""

    template = 'lab/component/deck.html'

    size: int = Glue.attr(3, parameter=True)
    touches: int = Glue.attr(0)
    cards_counted: int = Glue.attr(0)

    @property
    def keys(self) -> range:
        return range(self.size)

    @Glue.listener(CardComponent.counted)
    def card_counted(self) -> None:
        """A listener hears only descendants, so this is the deck's own cards."""
        self.cards_counted += 1

    @Glue.attr
    def touch(self) -> None:
        """Changes nothing the cards see, so its re-render keeps every card."""
        self.touches += 1

    @Glue.attr
    def grow(self) -> None:
        self.size += 1

    @Glue.attr
    def shrink(self) -> None:
        self.size = max(self.size - 1, 0)

    @Glue.attr
    def open_card(self) -> CardComponent:
        return CardComponent(start=self.size)


class TreeComponent(Glue.Component):
    """A node with ``fanout`` children, ``depth`` levels deep."""

    template = 'lab/component/tree.html'

    depth: int = Glue.attr(0, parameter=True)
    fanout: int = Glue.attr(2, parameter=True)
    touches: int = Glue.attr(0)

    @property
    def branches(self) -> range:
        return range(self.fanout if self.depth > 0 else 0)

    @Glue.attr
    def touch(self) -> None:
        self.touches += 1


class TallyComponent(Glue.Component):
    """Re-renders whenever any card on the page counts: ``rerender_on`` hears the whole page."""

    template = 'lab/component/tally.html'
    rerender_on = (CardComponent.counted,)
