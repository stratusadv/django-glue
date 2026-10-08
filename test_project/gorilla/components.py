from typing import Any

from django.http import HttpRequest

from django_glue import Glue, GlueOperation
from test_project.gorilla.forms import FightNameForm
from test_project.gorilla.models import Gorilla


class CounterCardComponent(Glue.Component):
    template = 'gorilla/component/counter_card.html'

    start: int = Glue.attr(parameter=True)
    count: int = Glue.attr(0, editable=True)
    counted = Glue.event()

    def __post_init__(self, request: HttpRequest) -> None:
        self.count = self.start

    @Glue.attr
    def increment(self) -> int:
        self.count += 1
        self.counted(value=self.count)
        return self.count


class RequestCounterCardComponent(CounterCardComponent):
    start: int = Glue.attr(0, parameter=True)

    def __post_init__(self, request: HttpRequest) -> None:
        self.start = int(request.GET['start'])
        self.access = Glue.Access.CHANGE
        super().__post_init__(request)


class GreetingCounterCardComponent(CounterCardComponent):
    greeting: str = Glue.attr('')

    def __post_init__(self, request: HttpRequest, visitor: Any = 'stranger') -> None:
        super().__post_init__(request)
        self.greeting = f'Hello, {visitor}'


class LaidOutCounterCardComponent(CounterCardComponent):
    view_template = 'gorilla/page/component_card_page.html'


class ProtectedCounterCardComponent(CounterCardComponent):
    def is_authorized(self, request: HttpRequest, operation: GlueOperation) -> bool:
        _ = operation
        return request.user.is_authenticated


class CounterDashboardComponent(Glue.Component):
    template = 'gorilla/component/counter_dashboard.html'

    starts: list[int] = Glue.attr(default_factory=lambda: [2, 5])

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


class GorillaFightsEditorComponent(Glue.Component):
    template = 'gorilla/component/fights_editor.html'

    @Glue.ComponentParameter
    def gorilla(self, pk: int) -> Gorilla:
        return Gorilla.objects.get(pk=pk)

    @Glue.property
    def fights(self) -> Glue.FormSet:
        # Whoever may change the gorilla may edit and remove its fights.
        can_change = self.access.has_access(Glue.Access.CHANGE)
        return Glue.FormSet(
            FightNameForm,
            instances=self.gorilla.fights_as_red_corner.order_by('pk'),
            # A new fight belongs to this gorilla and starts as a sparring
            # match against itself; the form exposes neither corner.
            new_row_defaults={'red_corner': self.gorilla.pk, 'blue_corner': self.gorilla.pk},
            access=Glue.Access.DELETE if can_change else Glue.Access.VIEW,
            can_delete=True,
        )

    checks: int = Glue.attr(0, editable=True)

    @Glue.attr
    def check(self) -> None:
        # Changes a retained value, so the component re-renders around its
        # formset child.
        self.checks += 1


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
