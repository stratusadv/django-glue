"""A Django form field as a component value attribute's type (ADR 051)."""

from __future__ import annotations

import datetime
from typing import Any

import pytest
from django import forms
from django.db import models

from django_glue import Glue
from django_glue.access import GlueAccess
from django_glue.exceptions import GlueRequestError, GlueRequestErrorCode
from django_glue.glue.components import Component
from django_glue.glue.objects.django.form.object import FormGlue
from django_glue.glue.policy import GluePolicy
from django_glue.templatetags.django_glue import glue_field_metadata_path
from django_glue.tests.glue.test_callable_parameters import call_context
from test_project.gorilla.models import Skill


class RosterSortChoices(models.TextChoices):
    NAME = 'name', 'Name'
    AGE = 'age', 'Age'


class RosterComponent(Component):
    template = 'glue_template_test.html'

    # Hinted with what the field cleans to; the field, not the hint, checks the value.
    sort: RosterSortChoices = Glue.ComponentField(forms.TypedChoiceField(
        choices=RosterSortChoices.choices,
        coerce=RosterSortChoices,
        initial=RosterSortChoices.NAME,
        label='Sort by',
    ))
    since = Glue.ComponentField(forms.DateField(initial=datetime.date(2026, 9, 1)))

    @Glue.attr(skip_rerender=True)
    def read(self) -> dict[str, Any]:
        return {
            'sort': self.sort,
            'sort_is_a_choice': isinstance(self.sort, RosterSortChoices),
            'since_is_a_date': isinstance(self.since, datetime.date),
        }


@pytest.fixture
def roster(mock_request) -> RosterComponent:
    return Glue.object(mock_request, RosterComponent())


def call(
    roster: RosterComponent,
    attribute: str,
    *,
    updates: dict[str, Any] | None = None,
    token: str | None = None,
) -> dict[str, Any]:
    context = call_context(roster, attribute, updates=updates)
    if token is not None:
        context = context.model_copy(update={'target_glue_policy': GluePolicy.from_token(token)})
    rebuilt = RosterComponent.from_attribute_call_resolver_context(context)
    entry, _introduced = rebuilt.process_attribute_call(context)
    return entry


def test_the_attribute_reads_its_cleaned_default(roster) -> None:
    assert roster.sort is RosterSortChoices.NAME
    assert roster.since == datetime.date(2026, 9, 1)


def test_an_assigned_value_is_held_cleaned(roster) -> None:
    roster.sort = 'age'
    roster.since = '2026-10-31'

    assert roster.sort is RosterSortChoices.AGE
    assert roster.since == datetime.date(2026, 10, 31)


def test_the_browser_and_the_token_carry_the_prepared_value(roster) -> None:
    signed = GluePolicy.from_token(roster.policy.token).state_snapshot

    assert signed == {'sort': 'name', 'since': '2026-09-01'}


def test_an_update_is_cleaned_before_the_component_reads_it(roster) -> None:
    entry = call(roster, 'read', updates={'sort': 'age', 'since': '2026-10-31'})

    assert entry['result'] == {'sort': 'age', 'sort_is_a_choice': True, 'since_is_a_date': True}
    assert GluePolicy.from_token(entry['policy_token']).state_snapshot['since'] == '2026-10-31'


@pytest.mark.parametrize('updates', [{'sort': 'weight'}, {'since': 'tomorrow'}, {'sort': ['age']}])
def test_an_update_the_field_refuses_is_refused(roster, updates) -> None:
    with pytest.raises(GlueRequestError) as refused:
        call(roster, 'read', updates=updates)

    assert refused.value.code == GlueRequestErrorCode.INVALID_UPDATES


def test_a_value_restored_from_the_token_is_cleaned(roster) -> None:
    sorted_by_age = call(roster, 'read', updates={'sort': 'age'})

    later = call(roster, 'read', token=sorted_by_age['policy_token'])

    assert later['result'] == {'sort': 'age', 'sort_is_a_choice': True, 'since_is_a_date': True}


def test_the_browser_is_told_the_field_as_a_form_would_tell_it(roster) -> None:
    assert roster.get_static_data()['value_attributes']['sort'] == {
        'value_path': 'sort',
        'namespace': 'field',
        'type': 'TypedChoiceField',
        'label': 'Sort by',
        'required': True,
        'help_text': '',
        'editable': True,
        'disabled': False,
        'choices': [{'value': 'name', 'label': 'Name'}, {'value': 'age', 'label': 'Age'}],
        'widget': 'Select',
    }


def test_the_field_reports_no_errors_of_its_own(roster) -> None:
    assert 'value_attributes' not in roster.get_computed_data(include_all=True)


def test_a_field_include_finds_the_description_on_the_component() -> None:
    assert glue_field_metadata_path('component.sort') == 'component.$fields.sort'


@pytest.mark.parametrize(
    ('field', 'reason'),
    [
        (forms.ModelChoiceField(queryset=Skill.objects.all(), required=False), 'narrows its queryset'),
        (forms.ModelMultipleChoiceField(queryset=Skill.objects.all(), required=False), 'narrows its queryset'),
        (forms.FileField(required=False), 'a file is uploaded'),
        (forms.CharField(widget=forms.PasswordInput, required=False), 'a write-only value'),
    ],
)
def test_a_field_a_value_cannot_stand_alone_in_is_refused_with_its_class(field, reason) -> None:
    with pytest.raises(TypeError, match=reason):
        class RefusedComponent(Component):
            template = 'glue_template_test.html'

            refused = Glue.ComponentField(field)


def test_a_password_field_that_renders_its_value_is_held(mock_request) -> None:
    class PinComponent(Component):
        template = 'glue_template_test.html'

        pin = Glue.ComponentField(forms.CharField(widget=forms.PasswordInput(render_value=True), initial='1234'))

    assert Glue.object(mock_request, PinComponent()).policy.state_snapshot['pin'] == '1234'


def test_a_callable_initial_is_called_for_each_component(mock_request) -> None:
    days = iter([datetime.date(2026, 11, 1), datetime.date(2026, 11, 2)])

    class DiaryComponent(Component):
        template = 'glue_template_test.html'

        day = Glue.ComponentField(forms.DateField(initial=lambda: next(days)))

    assert Glue.object(mock_request, DiaryComponent()).day == datetime.date(2026, 11, 1)
    assert Glue.object(mock_request, DiaryComponent()).day == datetime.date(2026, 11, 2)


def test_a_disabled_field_is_drawn_but_not_editable(mock_request) -> None:
    class LockedComponent(Component):
        template = 'glue_template_test.html'

        sort = Glue.ComponentField(forms.ChoiceField(choices=[('name', 'Name')], initial='name', disabled=True))

    locked = Glue.object(mock_request, LockedComponent())
    description = locked.get_static_data()['value_attributes']['sort']

    assert (description['editable'], description['disabled']) == (False, True)


def test_an_optional_field_with_no_initial_starts_empty(mock_request) -> None:
    class NoteComponent(Component):
        template = 'glue_template_test.html'

        note = Glue.ComponentField(forms.CharField(required=False))

    assert Glue.object(mock_request, NoteComponent()).note == ''


def test_a_required_field_with_no_initial_is_refused() -> None:
    with pytest.raises(TypeError, match='needs an initial'):
        Glue.ComponentField(forms.CharField())


def test_only_a_component_may_hold_one() -> None:
    # Python 3.11 wraps a __set_name__ error in RuntimeError; 3.12 and later raise it as is.
    with pytest.raises((RuntimeError, TypeError)) as raised:
        class NotAComponent:
            sort = Glue.ComponentField(forms.CharField(required=False))

    error = raised.value.__cause__ or raised.value
    assert isinstance(error, TypeError)
    assert 'is not a Component' in str(error)


def test_only_a_form_field_is_taken() -> None:
    with pytest.raises(TypeError, match='takes a Django form field'):
        Glue.ComponentField(models.CharField(max_length=10))


def test_a_forms_own_fields_still_hold_raw_values(mock_request) -> None:
    class AgeForm(forms.Form):
        age = forms.IntegerField()

    form_glue = FormGlue(AgeForm(), name='age-form', access=GlueAccess.CHANGE)
    age = Glue.object(mock_request, form_glue)._bound_attributes['age']

    assert age.coerce_update('3') == '3'
    assert age.coerce_update('three') == 'three'
    assert age.decode_retained('3') == '3'
