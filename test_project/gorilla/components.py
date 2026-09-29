from typing import Any

from django.http import HttpRequest

from django_glue import Glue, GlueOperation


class CounterCardComponent(Glue.Component):
    template = 'gorilla/component/counter_card.html'

    start: int = Glue.attr(parameter=True)
    count: int = Glue.attr(0, editable=True)
    counted = Glue.event()

    def mount(self) -> None:
        self.count = self.start

    @Glue.attr
    def increment(self) -> int:
        self.count += 1
        self.counted(value=self.count)
        return self.count


class LaidOutCounterCardComponent(CounterCardComponent):
    layout_template = 'gorilla/page/component_card_page.html'


class ProtectedCounterCardComponent(CounterCardComponent):
    def is_authorized(self, request: HttpRequest, operation: GlueOperation) -> bool:
        _ = operation
        return request.user.is_authenticated


class CounterDashboardComponent(Glue.Component):
    template = 'gorilla/component/counter_dashboard.html'

    starts: list[int] = Glue.attr(default_factory=lambda: [2, 5])

    def get_context_data(self) -> dict:
        return {'component': self, 'starts': self.starts}

    @Glue.attr
    def drop_first(self) -> None:
        self.starts = [5]


class RerenderingCounterDashboardComponent(CounterDashboardComponent):
    rerender_on = (CounterCardComponent.counted,)


class CounterTallyComponent(Glue.Component):
    template = 'gorilla/component/counter_tally.html'

    starts: list[int] = Glue.attr(default_factory=lambda: [2, 5])
    last_counted_start: int = Glue.attr(0)
    counted_since_mount: int = Glue.attr(0)

    def get_context_data(self) -> dict:
        return {'component': self, 'starts': self.starts}

    @Glue.listener(CounterCardComponent.counted)
    def card_counted(self, event: Glue.ReceivedEvent[CounterCardComponent]) -> None:
        self.last_counted_start = event.source.start

    @Glue.listener(CounterCardComponent.counted)
    def tally(self) -> None:
        self.counted_since_mount += 1

    @Glue.attr
    def open_card(self) -> CounterCardComponent:
        return CounterCardComponent(start=9)


class QuietCounterTallyComponent(CounterTallyComponent):
    @Glue.listener(CounterCardComponent.counted, skip_rerender=True)
    def card_counted(self, event: Glue.ReceivedEvent[CounterCardComponent]) -> None:
        pass

    @Glue.listener(CounterCardComponent.counted, skip_rerender=True)
    def tally(self) -> None:
        pass


class GuardedCounterTallyComponent(CounterTallyComponent):
    @Glue.listener(CounterCardComponent.counted, required_access=Glue.Access.CHANGE)
    def tally(self) -> None:
        self.counted_since_mount += 1


class CounterBadgeComponent(Glue.Component):
    template = 'glue_template_test.html'


class CounterBadgeOwnerComponent(Glue.Component):
    template = 'glue_template_test.html'

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.badge_value = CounterBadgeComponent()

    @Glue.property
    def badge(self) -> CounterBadgeComponent:
        return self.badge_value
