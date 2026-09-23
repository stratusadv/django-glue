from django_glue import Glue


class CounterCard(Glue.Component):
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


class CounterDashboard(Glue.Component):
    template = 'gorilla/component/counter_dashboard.html'

    starts: list[int] = Glue.attr(default_factory=lambda: [2, 5])

    def get_context_data(self) -> dict:
        return {'component': self, 'starts': self.starts}

    @Glue.attr
    def drop_first(self) -> Glue.Response:
        self.starts = [5]
        return self.render()
