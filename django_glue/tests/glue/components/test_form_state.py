"""A Django form held as a component's editable state (ADR 042)."""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Any

import pytest
from django import forms

from django_glue import Glue
from django_glue.exceptions import GlueRequestError, GlueRequestErrorCode
from django_glue.glue.components import Component
from django_glue.glue.policy import GluePolicy
from django_glue.tests.glue.test_callable_parameters import call_context
from test_project.gorilla.models import Skill

INITIAL_FILTERS = {'search': None, 'styles': None, 'sort': 'name'}
BOXERS_BY_AGE = {'search': 'ko', 'styles': ['boxing'], 'sort': 'age'}


class RosterFilterForm(forms.Form):
    search = forms.CharField(required=False)
    styles = forms.MultipleChoiceField(
        choices=[('boxing', 'Boxing'), ('wrestling', 'Wrestling')],
        required=False,
    )
    sort = forms.ChoiceField(choices=[('name', 'Name'), ('age', 'Age')], initial='name')

    def clean(self) -> dict[str, Any]:
        cleaned_data = super().clean()
        if cleaned_data.get('search') == 'everything':
            raise forms.ValidationError('Narrow the search.')
        return cleaned_data


class SkillFilterForm(forms.ModelForm):
    class Meta:
        model = Skill
        fields = ('difficulty',)


@dataclass(frozen=True)
class ReportWindow:
    start: datetime.date
    end: datetime.date


class RosterComponent(Component):
    template = 'glue_component_greeting_test.html'

    filters: RosterFilterForm = Glue.attr(editable=True)
    window: ReportWindow = Glue.attr(
        default_factory=lambda: ReportWindow(datetime.date(2026, 9, 1), datetime.date(2026, 9, 30)),
        editable=True,
    )

    @property
    def greeting(self) -> str:
        if not self.filters.is_valid():
            return 'invalid'
        filters = self.filters.cleaned_data
        return f'{filters["search"]}|{",".join(filters["styles"])}|{filters["sort"]}'

    @Glue.attr
    def ping(self) -> str:
        return 'pong'

    @Glue.attr
    def reset(self) -> None:
        self.filters = RosterFilterForm()

    @Glue.attr(skip_rerender=True)
    def days(self) -> int:
        return (self.window.end - self.window.start).days

    @Glue.attr(skip_rerender=True)
    def describe(self, filters: RosterFilterForm) -> str:
        assert filters.is_valid()
        return filters.cleaned_data['sort']


@pytest.fixture
def roster(mock_request) -> RosterComponent:
    return Glue.object(mock_request, RosterComponent())


def call(
    roster: RosterComponent,
    attribute: str | None,
    *,
    updates: dict[str, Any] | None = None,
    kwargs: dict[str, Any] | None = None,
    token: str | None = None,
) -> dict[str, Any]:
    context = call_context(roster, attribute, updates=updates, kwargs=kwargs)
    if token is not None:
        context = context.model_copy(update={'target_glue_policy': GluePolicy.from_token(token)})
    rebuilt = RosterComponent.from_attribute_call_resolver_context(context)
    entry, _introduced = rebuilt.process_attribute_call(context)
    return entry


def signed_filters(entry: dict[str, Any]) -> dict[str, Any]:
    return GluePolicy.from_token(entry['policy_token']).state_snapshot['filters']


def test_the_form_is_bound_to_its_initial_values_before_the_browser_sends_any(roster) -> None:
    assert roster.filters.is_valid()
    assert roster.filters.cleaned_data == {'search': '', 'styles': [], 'sort': 'name'}
    assert roster.policy.state_snapshot['filters'] == INITIAL_FILTERS


def test_every_read_in_a_request_is_the_same_form(roster) -> None:
    assert roster.filters is roster.filters


def test_a_declared_default_stands_in_for_the_forms_own(mock_request) -> None:
    class ByAgeComponent(Component):
        template = 'glue_template_test.html'

        filters: RosterFilterForm = Glue.attr(
            default_factory=lambda: RosterFilterForm(initial={'sort': 'age'}),
            editable=True,
        )

    by_age = Glue.object(mock_request, ByAgeComponent())

    assert by_age.policy.state_snapshot['filters'] == {**INITIAL_FILTERS, 'sort': 'age'}


def test_an_attribute_of_another_type_still_has_no_default(mock_request) -> None:
    class CounterComponent(Component):
        template = 'glue_template_test.html'

        count: int = Glue.attr(editable=True)

    counter = Glue.object(mock_request, CounterComponent())

    assert counter.count is None
    assert counter.policy.state_snapshot['count'] is None


def test_the_browser_is_told_each_field_as_a_glued_form_would_tell_it(roster) -> None:
    described = roster.get_static_data()['value_attributes']['filters']

    assert described['value_path'] == 'filters'
    assert described['editable'] is True
    assert described['fields']['sort'] == {
        'namespace': 'field',
        'type': 'ChoiceField',
        'label': '',
        'required': True,
        'help_text': '',
        'editable': True,
        'disabled': False,
        'choices': [{'value': 'name', 'label': 'Name'}, {'value': 'age', 'label': 'Age'}],
        'widget': 'Select',
    }
    assert described['fields']['styles']['type'] == 'MultipleChoiceField'


def test_an_update_reaches_the_form_and_is_signed(roster) -> None:
    entry = call(roster, 'ping', updates={'filters': BOXERS_BY_AGE})

    assert '>ko|boxing|age</span>' in entry['html']
    assert signed_filters(entry) == BOXERS_BY_AGE


def test_a_refresh_keeps_the_filters(roster) -> None:
    entry = call(roster, None, updates={'filters': BOXERS_BY_AGE})

    assert '>ko|boxing|age</span>' in entry['html']
    assert signed_filters(entry) == BOXERS_BY_AGE


def test_the_signed_filters_hold_on_a_later_request_that_sends_none(roster) -> None:
    filtered = call(roster, 'ping', updates={'filters': BOXERS_BY_AGE})

    later = call(roster, 'ping', token=filtered['policy_token'])

    assert '>ko|boxing|age</span>' in later['html']


def test_a_value_the_form_refuses_is_an_error_on_its_field(roster) -> None:
    entry = call(roster, 'ping', updates={'filters': {**BOXERS_BY_AGE, 'sort': 'weight'}})

    assert '>invalid</span>' in entry['html']
    computed = entry['computed_data']['value_attributes']['filters']
    assert computed['errors'] == []
    assert list(computed['field_errors']) == ['sort']


def test_an_error_of_the_whole_form_is_reported_beside_its_fields(roster) -> None:
    entry = call(roster, 'ping', updates={'filters': {**BOXERS_BY_AGE, 'search': 'everything'}})

    assert entry['computed_data']['value_attributes']['filters'] == {
        'errors': ['Narrow the search.'],
        'field_errors': {},
    }


def test_no_errors_are_reported_for_a_form_nothing_validated(mock_request) -> None:
    class UnreadComponent(Component):
        template = 'glue_template_test.html'

        filters: RosterFilterForm = Glue.attr(default_factory=RosterFilterForm, editable=True)

    unread = Glue.object(mock_request, UnreadComponent())

    assert unread.get_computed_data(include_all=True)['value_attributes']['filters'] == {
        'errors': [],
        'field_errors': {},
    }
    assert unread.filters._errors is None


def test_a_derived_value_named_fields_keeps_its_own_key(mock_request: Any) -> None:
    class FieldsComponent(Component):
        template = 'glue_template_test.html'

        filters: RosterFilterForm = Glue.attr(default_factory=RosterFilterForm, editable=True)

        @Glue.property
        def fields(self) -> list[str]:
            return ['search', 'sort']

    component = Glue.object(mock_request, FieldsComponent())

    computed = component.get_computed_data(include_all=True)

    assert computed['values'] == {'fields': ['search', 'sort']}
    assert computed['value_attributes'] == {'filters': {'errors': [], 'field_errors': {}}}


@pytest.mark.parametrize('filters', [{'search': 'ko', 'rank': 1}, ['ko'], 'ko', None])
def test_state_that_is_not_the_forms_fields_is_refused(roster, filters) -> None:
    with pytest.raises(GlueRequestError) as refused:
        call(roster, 'ping', updates={'filters': filters})

    assert refused.value.code == GlueRequestErrorCode.INVALID_UPDATES


def test_an_unbound_form_assigned_in_a_call_is_bound_to_its_initial_values(roster) -> None:
    filtered = call(roster, 'ping', updates={'filters': BOXERS_BY_AGE})

    entry = call(roster, 'reset', token=filtered['policy_token'])

    assert '>||name</span>' in entry['html']
    assert signed_filters(entry) == INITIAL_FILTERS


def test_a_form_class_types_a_callable_argument(roster) -> None:
    entry = call(roster, 'describe', kwargs={'filters': BOXERS_BY_AGE})

    assert entry['result'] == 'age'


def test_a_model_form_without_an_instance_is_held_like_any_form(mock_request, db) -> None:
    class SkillListComponent(Component):
        template = 'glue_template_test.html'

        filters: SkillFilterForm = Glue.attr(default_factory=SkillFilterForm, editable=True)

    skills = Glue.object(mock_request, SkillListComponent())

    assert skills.policy.state_snapshot['filters'] == {'difficulty': 1}
    assert skills.filters.is_valid()
    assert skills.filters.cleaned_data == {'difficulty': 1}


def test_a_model_form_over_a_saved_record_is_refused(mock_request, db) -> None:
    class SkillListComponent(Component):
        template = 'glue_template_test.html'

        filters: SkillFilterForm = Glue.attr(default_factory=SkillFilterForm, editable=True)

    skills = Glue.object(mock_request, SkillListComponent())
    jab = Skill.objects.create(name='Jab')

    with pytest.raises(TypeError, match='a form that edits a record is a Glue.child'):
        skills.filters = SkillFilterForm(instance=jab)


@pytest.mark.parametrize(
    ('field', 'reason'),
    [
        (forms.FileField(), 'a file is uploaded'),
        (forms.CharField(widget=forms.PasswordInput), 'a write-only value'),
        (forms.ModelChoiceField(queryset=Skill.objects.all()), 'nothing narrows its queryset'),
    ],
)
def test_a_form_with_a_field_that_cannot_be_state_is_refused_when_first_used(
    mock_request,
    field,
    reason,
) -> None:
    refused_form = type('RefusedForm', (forms.Form,), {'refused': field})
    # Built by hand so the type hint is the class itself, not a name this module cannot resolve.
    refused_component = type(
        'RefusedComponent',
        (Component,),
        {
            'template': 'glue_template_test.html',
            '__annotations__': {'filters': refused_form},
            'filters': Glue.attr(default_factory=refused_form, editable=True),
        },
    )

    with pytest.raises(TypeError, match=reason):
        Glue.object(mock_request, refused_component()).policy  # noqa: B018


def test_a_form_that_needs_constructor_arguments_is_refused_when_first_used(mock_request) -> None:
    class ScopedFilterForm(RosterFilterForm):
        def __init__(self, *args: Any, company_id: int, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            self.company_id = company_id

    scoped_component = type(
        'ScopedComponent',
        (Component,),
        {
            'template': 'glue_template_test.html',
            '__annotations__': {'filters': ScopedFilterForm},
            'filters': Glue.attr(editable=True),
        },
    )

    with pytest.raises(TypeError, match='its __init__ requires company_id'):
        Glue.object(mock_request, scoped_component()).policy  # noqa: B018


def test_only_an_attribute_typed_as_a_form_binds_one(mock_request) -> None:
    class UntypedComponent(Component):
        template = 'glue_template_test.html'

        stash = Glue.attr()

    untyped = UntypedComponent()
    untyped.stash = RosterFilterForm()

    assert untyped.stash.is_bound is False


def test_a_form_is_bound_whatever_value_adapters_the_declaration_names(mock_request) -> None:
    class OwnAdaptersComponent(Component):
        template = 'glue_template_test.html'

        filters: RosterFilterForm = Glue.attr(editable=True, value_adapters=[])

    own_adapters = Glue.object(mock_request, OwnAdaptersComponent())

    assert own_adapters.filters.is_bound
    assert own_adapters.policy.state_snapshot['filters'] == INITIAL_FILTERS


def test_a_value_only_its_type_can_write_is_dumped_and_restored_by_it(roster) -> None:
    assert roster.policy.state_snapshot['window'] == {'start': '2026-09-01', 'end': '2026-09-30'}

    entry = call(
        roster,
        'days',
        updates={'window': {'start': '2026-09-01', 'end': '2026-09-08'}},
    )

    assert entry['result'] == 7
