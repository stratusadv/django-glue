from __future__ import annotations

import datetime

import pytest
from django.template import Context, Template, TemplateSyntaxError
from django.test import RequestFactory

from django_glue import Glue
from django_glue.access import GlueAccess
from django_glue.exceptions import (
    GlueComponentKeyError,
    GlueComponentParameterError,
    GlueComponentRegistrationError,
    GlueComponentRootError,
)
from django_glue.glue.component.naming import canonical_key, derive_component_name
from django_glue.glue.context import GlueContextManager


class DayCard(Glue.Component):
    template = 'component/day_card.html'

    date: datetime.date = Glue.attr(parameter=True)


class WeekBoard(Glue.Component):
    template = 'component/week_board.html'

    label: str = Glue.attr(parameter=True)

    # A plain property stays server-internal; the template loops it to stamp
    # children, and the dates are the children's keys.
    @property
    def days(self) -> list[datetime.date]:
        return [datetime.date(2026, 9, 9), datetime.date(2026, 9, 10)]


@pytest.fixture
def request_with_session(db):
    request = RequestFactory().get('/')
    from django.contrib.sessions.middleware import SessionMiddleware

    SessionMiddleware(lambda _: None).process_request(request)
    request.session.create()

    return request


def render(source: str, request, **context) -> str:
    return Template('{% load django_glue %}' + source).render(
        Context({'request': request, **context}, use_l10n=False),
    )


class TestStamping:
    def test_stamping_renders_the_component_template(self, request_with_session) -> None:
        html = render(
            "{% glue_component 'day-card' date=date %}",
            request_with_session,
            date=datetime.date(2026, 9, 9),
        )

        assert 'day-card' in html
        assert 'x-data="{ component: Glue.component.' in html

    def test_stamping_registers_a_top_level_manifest(self, request_with_session) -> None:
        render(
            "{% glue_component 'day-card' date=date %}",
            request_with_session,
            date=datetime.date(2026, 9, 9),
        )

        glue_objects = GlueContextManager(request_with_session).glue_objects

        assert len(glue_objects) == 1
        assert isinstance(glue_objects[0], DayCard)
        assert glue_objects[0].date == datetime.date(2026, 9, 9)

    def test_parameters_keep_their_python_type(self, request_with_session) -> None:
        """A tag kwarg resolves through FilterExpression to a real value."""
        render(
            "{% glue_component 'day-card' date=date %}",
            request_with_session,
            date=datetime.date(2026, 9, 9),
        )

        stamped = GlueContextManager(request_with_session).glue_objects[0]

        assert isinstance(stamped.date, datetime.date)

    def test_undeclared_parameter_is_rejected(self, request_with_session) -> None:
        with pytest.raises(GlueComponentParameterError, match='undeclared'):
            render(
                "{% glue_component 'day-card' date=date colour='red' %}",
                request_with_session,
                date=datetime.date(2026, 9, 9),
            )

    def test_unregistered_tag_name_is_rejected(self, request_with_session) -> None:
        with pytest.raises(GlueComponentRegistrationError, match='No Glue component'):
            render("{% glue_component 'not-a-component' %}", request_with_session)

    def test_access_defaults_to_view(self, request_with_session) -> None:
        render(
            "{% glue_component 'day-card' date=date %}",
            request_with_session,
            date=datetime.date(2026, 9, 9),
        )

        assert GlueContextManager(request_with_session).glue_objects[0].access == GlueAccess.VIEW

    def test_access_is_overridable_at_the_stamp_site(self, request_with_session) -> None:
        render(
            "{% glue_component 'day-card' date=date access='change' %}",
            request_with_session,
            date=datetime.date(2026, 9, 9),
        )

        assert GlueContextManager(request_with_session).glue_objects[0].access == GlueAccess.CHANGE

    def test_the_binding_is_injected_into_the_template_s_own_root(
        self,
        request_with_session,
    ) -> None:
        """A component template is ordinary HTML and carries no Glue marker."""
        html = render(
            "{% glue_component 'day-card' date=date %}",
            request_with_session,
            date=datetime.date(2026, 9, 9),
        )
        stamped = GlueContextManager(request_with_session).glue_objects[0]

        assert f'<div class="day-card" x-data="{{ component: Glue.component.{stamped.name} }}"' in html
        assert f'data-glue="{stamped.name}"' in html

    def test_a_multi_root_component_template_is_rejected(
        self,
        request_with_session,
    ) -> None:
        class TwoRoots(Glue.Component):
            template = 'component/two_roots.html'

        with pytest.raises(GlueComponentRootError, match='more than one root'):
            render("{% glue_component 'two-roots' %}", request_with_session)


class TestKeys:
    def test_key_is_required_inside_a_loop(self, request_with_session) -> None:
        with pytest.raises(GlueComponentKeyError, match='needs key='):
            render(
                '{% for date in dates %}'
                "{% glue_component 'day-card' date=date %}"
                '{% endfor %}',
                request_with_session,
                dates=[datetime.date(2026, 9, 9), datetime.date(2026, 9, 10)],
            )

    def test_keyed_loop_stamps_distinct_components(self, request_with_session) -> None:
        render(
            '{% for date in dates %}'
            "{% glue_component 'day-card' date=date key=date %}"
            '{% endfor %}',
            request_with_session,
            dates=[datetime.date(2026, 9, 9), datetime.date(2026, 9, 10)],
        )

        names = [
            glue.name
            for glue in GlueContextManager(request_with_session).glue_objects
        ]

        assert len(names) == 2
        assert len(set(names)) == 2

    def test_key_is_not_required_outside_a_loop(self, request_with_session) -> None:
        render(
            "{% glue_component 'day-card' date=date %}",
            request_with_session,
            date=datetime.date(2026, 9, 9),
        )

        assert len(GlueContextManager(request_with_session).glue_objects) == 1

    def test_duplicate_key_under_one_parent_is_rejected(self, request_with_session) -> None:
        with pytest.raises(GlueComponentKeyError, match='share the key'):
            render(
                "{% glue_component 'day-card' date=date key=1 %}"
                "{% glue_component 'day-card' date=date key=1 %}",
                request_with_session,
                date=datetime.date(2026, 9, 9),
            )

    def test_loop_index_key_is_rejected_at_parse_time(self) -> None:
        with pytest.raises(TemplateSyntaxError, match='cannot key on a loop index'):
            Template(
                '{% load django_glue %}'
                '{% for date in dates %}'
                "{% glue_component 'day-card' date=date key=forloop.counter %}"
                '{% endfor %}'
            )

    def test_unusable_key_type_is_rejected(self, request_with_session) -> None:
        with pytest.raises(GlueComponentKeyError, match='immutable scalar'):
            render(
                "{% glue_component 'day-card' date=date key=bad %}",
                request_with_session,
                date=datetime.date(2026, 9, 9),
                bad=['a', 'list'],
            )


class TestNameDerivation:
    def test_names_are_stable_across_renders(self) -> None:
        """A name that changes per render creates a new proxy and defeats morph."""
        first = derive_component_name(parent_name='dash', tag_name='day-card', key=1)
        second = derive_component_name(parent_name='dash', tag_name='day-card', key=1)

        assert first == second

    def test_the_parent_segment_scopes_keys_to_siblings(self) -> None:
        """Two dashboards showing the same dates must not collide."""
        first = derive_component_name(parent_name='dash_a', tag_name='day-card', key=1)
        second = derive_component_name(parent_name='dash_b', tag_name='day-card', key=1)

        assert first != second

    def test_distinct_keys_derive_distinct_names(self) -> None:
        first = derive_component_name(parent_name='dash', tag_name='day-card', key=1)
        second = derive_component_name(parent_name='dash', tag_name='day-card', key=2)

        assert first != second

    def test_the_name_is_a_javascript_safe_identifier(self) -> None:
        name = derive_component_name(
            parent_name='',
            tag_name='time-tracker.day-card',
            key=1,
        )

        assert name.replace('_', 'x').isalnum()
        assert name.startswith('time_tracker_day_card_')

    @pytest.mark.parametrize(
        ('first', 'second'),
        [
            (1, '1'),
            (1, (1,)),
            (True, 1),
            ((1, '2'), ('1', 2)),
        ],
    )
    def test_keys_of_different_types_do_not_collide(self, first, second) -> None:
        assert canonical_key(first) != canonical_key(second)

    def test_a_date_key_is_canonicalised_by_value_not_repr(self) -> None:
        assert canonical_key(datetime.date(2026, 9, 9)) == 'date:2026-09-09'


class TestNesting:
    def test_a_nested_stamp_reads_its_parent_from_context(
        self,
        request_with_session,
    ) -> None:
        """week_board.html stamps day-card, so the child's name is parent-scoped."""
        render(
            "{% glue_component 'week-board' label='Week 37' %}",
            request_with_session,
        )

        glue_objects = GlueContextManager(request_with_session).glue_objects
        names = {glue.name for glue in glue_objects}
        board = next(glue for glue in glue_objects if isinstance(glue, WeekBoard))
        cards = [glue for glue in glue_objects if isinstance(glue, DayCard)]

        assert len(cards) == 2
        assert len(names) == 3

        expected = {
            derive_component_name(
                parent_name=board.name,
                tag_name='day-card',
                key=day,
            )
            for day in board.days
        }

        assert {card.name for card in cards} == expected


class TestBlockForm:
    def test_the_block_form_names_slots_explicitly(self) -> None:
        with pytest.raises(TemplateSyntaxError, match='Slots are not supported yet'):
            Template(
                '{% load django_glue %}'
                "{% glue_component 'day-card' %}inner{% endglue_component %}"
            )


class TestTagSyntax:
    def test_the_component_tag_name_is_required(self) -> None:
        with pytest.raises(TemplateSyntaxError, match='needs a registered component'):
            Template('{% load django_glue %}{% glue_component %}')

    def test_extra_positional_arguments_are_rejected(self) -> None:
        with pytest.raises(TemplateSyntaxError, match='everything else as keywords'):
            Template("{% load django_glue %}{% glue_component 'day-card' oops %}")

    def test_duplicate_arguments_are_rejected(self) -> None:
        with pytest.raises(TemplateSyntaxError, match='duplicate argument'):
            Template(
                '{% load django_glue %}'
                "{% glue_component 'day-card' date=a date=b %}"
            )
