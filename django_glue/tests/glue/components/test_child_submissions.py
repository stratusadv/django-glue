from __future__ import annotations

from typing import Any

import pytest
from django.forms.formsets import all_valid

from django_glue import Glue
from django_glue.exceptions import GlueRequestError
from django_glue.glue.components import Component
from django_glue.glue.objects.django.form.object import FormGlue
from django_glue.glue.objects.django.formset import FormSetGlue
from django_glue.glue.policy import GluePolicy
from django_glue.tests.glue.test_callable_parameters import call_context
from test_project.fight.forms import ContactPromoterForm
from test_project.gorilla.forms import SkillForm

VALID_CONTACT = {
    'name': 'Koko',
    'email': 'koko@example.com',
    'subject': 'fighter',
    'message': 'I would like to register a fighter.',
}


class SkillFormSet(Glue.FormSet):
    form_class = SkillForm
    min_num = 1


class BoutCardComponent(Component):
    template = 'glue_template_test.html'

    @Glue.child
    def contact(self) -> FormGlue:
        return Glue.form(target=ContactPromoterForm(), access=self.access)

    @Glue.child
    def skills(self) -> FormSetGlue:
        return SkillFormSet(initial=[{'name': 'Jab'}], access=self.access)

    @Glue.child
    def terms(self) -> FormGlue:
        return Glue.form(target=ContactPromoterForm(), access=Glue.Access.VIEW)

    @Glue.attr(required_access=Glue.Access.CHANGE, skip_rerender=True)
    def send(self) -> dict[str, Any]:
        contact_form = self.contact
        contact = contact_form.validate()
        skills = self.skills.validate()

        return {
            'contact_valid': contact['valid'],
            'skills_valid': skills['valid'],
            'name': contact_form.bound_form.cleaned_data.get('name'),
            'skill_names': [form.bound_form.cleaned_data.get('name') for form in skills['form_list']],
        }

    @Glue.attr(required_access=Glue.Access.CHANGE, skip_rerender=True)
    def send_all(self) -> dict[str, Any]:
        if not all_valid([self.contact, self.skills]):
            return {}

        return {'contact': self.contact.cleaned_data, 'skills': self.skills.cleaned_data}

    @Glue.attr(required_access=Glue.Access.CHANGE, skip_rerender=True)
    def read_terms(self) -> bool:
        return self.terms.validate()['valid']

    @Glue.attr(required_access=Glue.Access.CHANGE, skip_rerender=True)
    def ping(self) -> str:
        return 'pong'


@pytest.fixture
def card(mock_request) -> BoutCardComponent:
    return Glue.object(mock_request, BoutCardComponent(access=Glue.Access.CHANGE))


def tokens_by_address(card: BoutCardComponent) -> dict[str, str]:
    return {entry['address']: entry['policy_token'] for entry in card._serialized_child_entries()}


def child_submissions(
    card: BoutCardComponent,
    *,
    contact: dict[str, Any] | None = None,
    skill: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """What the browser submits for the card's writable children, with these changes."""
    tokens = tokens_by_address(card)
    children = card.policy.children
    skills_token = tokens[children['skills']]
    rows = GluePolicy.from_token(skills_token).children

    return {
        'contact': {'policy_token': tokens[children['contact']], 'updates': contact or {}},
        'skills': {
            'policy_token': skills_token,
            'updates': {},
            'forms': {
                key: {'policy_token': tokens[address], 'updates': skill or {}}
                for key, address in rows.items()
            },
        },
    }


def call(
    card: BoutCardComponent,
    attribute: str,
    submissions: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    context = call_context(card, attribute).model_copy(update={'child_submissions': submissions or {}})
    rebuilt = BoutCardComponent.from_attribute_call_resolver_context(context)
    return rebuilt.process_attribute_call(context)


def test_a_call_reads_its_children_with_the_users_changes(card) -> None:
    entry, _ = call(
        card,
        'send',
        child_submissions(card, contact=VALID_CONTACT, skill={'name': 'Hook', 'difficulty': 2, 'level': 3}),
    )

    assert entry['result'] == {
        'contact_valid': True,
        'skills_valid': True,
        'name': 'Koko',
        'skill_names': ['Hook'],
    }


def test_djangos_all_valid_checks_children_and_their_cleaned_data_follows(card) -> None:
    entry, _ = call(
        card,
        'send_all',
        child_submissions(card, contact=VALID_CONTACT, skill={'name': 'Hook', 'difficulty': 2, 'level': 3}),
    )

    assert entry['result']['contact']['name'] == 'Koko'
    assert [row['name'] for row in entry['result']['skills']] == ['Hook']


def test_all_valid_validates_every_child_when_the_first_fails(card) -> None:
    entry, introduced = call(
        card,
        'send_all',
        child_submissions(card, contact={'email': 'not-an-email'}, skill={'name': ''}),
    )

    assert entry['result'] == {}
    errors_by_address = {
        item['address']: item['computed_data'].get('fields', {})
        for item in introduced
    }
    assert errors_by_address[card.policy.children['contact']]['email']['errors']
    skills_policy = GluePolicy.from_token(tokens_by_address(card)[card.policy.children['skills']])
    [row_address] = skills_policy.children.values()
    assert errors_by_address[row_address]['name']['errors']


def test_cleaned_data_is_refused_before_validation(mock_request) -> None:
    form = Glue.form(target=ContactPromoterForm())

    with pytest.raises(AttributeError, match='before it is validated'):
        _ = form.cleaned_data


def test_a_read_childs_errors_answer_on_its_own_entry(card) -> None:
    entry, introduced = call(
        card,
        'send',
        child_submissions(card, contact={**VALID_CONTACT, 'email': 'not-an-email'}),
    )

    assert entry['result']['contact_valid'] is False
    contact_entry = next(item for item in introduced if item['address'] == card.policy.children['contact'])
    assert contact_entry['computed_data']['fields']['email']['errors']
    assert contact_entry['computed_data']['fields']['name']['errors'] == []


def test_a_read_formset_answers_with_its_rows(card) -> None:
    _, introduced = call(card, 'send', child_submissions(card, contact=VALID_CONTACT))

    addresses = [item['address'] for item in introduced]
    skills_policy = GluePolicy.from_token(tokens_by_address(card)[card.policy.children['skills']])
    assert card.policy.children['skills'] in addresses
    assert set(skills_policy.children.values()) <= set(addresses)
    assert len(addresses) == len(set(addresses))


def test_a_call_that_reads_no_child_is_unaffected_by_a_bad_submission(card) -> None:
    entry, introduced = call(card, 'ping', {'contact': {'policy_token': 'not-a-token'}})

    assert entry['result'] == 'pong'
    assert introduced == []


def test_a_call_without_submissions_reads_fresh_children(card) -> None:
    entry, _ = call(card, 'send')

    assert entry['result']['contact_valid'] is False
    assert entry['result']['name'] is None


def test_a_token_from_another_slot_is_refused(card) -> None:
    submissions = child_submissions(card, contact=VALID_CONTACT)
    submissions['contact']['policy_token'] = tokens_by_address(card)[card.policy.children['terms']]

    with pytest.raises(GlueRequestError):
        call(card, 'send', submissions)


def test_a_malformed_submission_is_refused_when_read(card) -> None:
    with pytest.raises(GlueRequestError):
        call(card, 'send', {'contact': {'policy_token': 'not-a-token'}})


def test_a_view_only_child_cannot_be_submitted(card) -> None:
    terms_token = tokens_by_address(card)[card.policy.children['terms']]

    with pytest.raises(GlueRequestError):
        call(card, 'read_terms', {'terms': {'policy_token': terms_token, 'updates': VALID_CONTACT}})


def test_the_browser_is_told_which_children_submit_with_their_owner(card) -> None:
    children = card.get_static_data()['children']

    assert children['contact']['submits_with_owner'] is True
    assert children['skills']['submits_with_owner'] is True


def test_a_property_child_does_not_submit_with_its_owner(mock_request) -> None:
    with pytest.warns(DeprecationWarning, match='Glue.child'):
        class LegacyCardComponent(Component):
            template = 'glue_template_test.html'

            @Glue.property
            def contact(self) -> FormGlue:
                return Glue.form(target=ContactPromoterForm(), access=self.access)

            @Glue.attr(required_access=Glue.Access.CHANGE, skip_rerender=True)
            def send(self) -> bool:
                return self.contact.validate()['valid']

    legacy = Glue.object(mock_request, LegacyCardComponent(access=Glue.Access.CHANGE))
    assert 'submits_with_owner' not in legacy.get_static_data()['children']['contact']

    contact_token = tokens_by_address(legacy)[legacy.policy.children['contact']]
    context = call_context(legacy, 'send').model_copy(update={
        'child_submissions': {'contact': {'policy_token': contact_token, 'updates': VALID_CONTACT}},
    })
    rebuilt = LegacyCardComponent.from_attribute_call_resolver_context(context)
    entry, _ = rebuilt.process_attribute_call(context)

    assert entry['result'] is False


def test_a_child_needs_a_glue_object_return_type() -> None:
    with pytest.raises(TypeError, match='return annotation'):
        class Untyped(Component):
            template = 'glue_template_test.html'

            @Glue.child
            def contact(self):
                return Glue.form(target=ContactPromoterForm())
