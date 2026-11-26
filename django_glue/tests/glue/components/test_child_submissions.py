from __future__ import annotations

from typing import Any

import pytest
from django import forms
from django.core.files.uploadedfile import SimpleUploadedFile
from django.forms.formsets import all_valid
from django.utils.datastructures import MultiValueDict

from django_glue import Glue
from django_glue.exceptions import GlueRequestError
from django_glue.glue.components import Component
from django_glue.glue.objects.django.form.object import FormGlue
from django_glue.glue.objects.django.formset import FormSetGlue
from django_glue.glue.objects.django.model.object import ModelGlue
from django_glue.glue.objects.django.queryset import QuerySetGlue
from django_glue.glue.operation import GlueOperation, GlueOperationKind
from django_glue.glue.policy import GluePolicy
from django_glue.glue.sequence import SequenceGlue
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
        contact_valid = contact_form.is_valid()
        skills = self.skills.validate()

        return {
            'contact_valid': contact_valid,
            'skills_valid': skills['valid'],
            'name': contact_form.cleaned_data.get('name'),
            'skill_names': [form.bound_form.cleaned_data.get('name') for form in skills['form_list']],
        }

    @Glue.attr(required_access=Glue.Access.CHANGE, skip_rerender=True)
    def send_all(self) -> dict[str, Any]:
        if not all_valid([self.contact, self.skills]):
            return {}

        return {'contact': self.contact.cleaned_data, 'skills': self.skills.cleaned_data}

    @Glue.attr(required_access=Glue.Access.CHANGE, skip_rerender=True)
    def read_terms(self) -> bool:
        return self.terms.is_valid()

    @Glue.attr(required_access=Glue.Access.CHANGE, skip_rerender=True)
    def ping(self) -> str:
        return 'pong'

    @Glue.attr(required_access=Glue.Access.CHANGE)
    def add_combination(self) -> None:
        for name in ('Hook', 'Uppercut'):
            self.skills.append(f'added-{name.lower()}', {'name': name})


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
        item['address']: item['computed_data'].get('value_attributes', {})
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
    assert contact_entry['computed_data']['value_attributes']['email']['errors']
    assert contact_entry['computed_data']['value_attributes']['name']['errors'] == []


def test_a_read_formset_answers_with_its_rows(card) -> None:
    _, introduced = call(card, 'send', child_submissions(card, contact=VALID_CONTACT))

    addresses = [item['address'] for item in introduced]
    skills_policy = GluePolicy.from_token(tokens_by_address(card)[card.policy.children['skills']])
    assert card.policy.children['skills'] in addresses
    assert set(skills_policy.children.values()) <= set(addresses)
    assert len(addresses) == len(set(addresses))


def test_rows_a_call_adds_to_a_child_formset_answer_at_the_formsets_keyed_addresses(card) -> None:
    _, introduced = call(card, 'add_combination', child_submissions(card, contact=VALID_CONTACT))

    entries = {item['address']: item for item in introduced}
    skills = entries[card.policy.children['skills']]
    rows = GluePolicy.from_token(skills['policy_token']).children
    assert set(rows) == {'0', 'added-hook', 'added-uppercut'}
    # Each row answers at the address the formset's children map binds it at, signed for it.
    assert rows['added-hook'] == f'{card.policy.children["skills"]}[added-hook]'
    for address in rows.values():
        assert GluePolicy.from_token(entries[address]['policy_token']).address == address


def test_a_call_that_reads_no_child_is_unaffected_by_a_bad_submission(card) -> None:
    entry, introduced = call(card, 'ping', {'contact': {'policy_token': 'not-a-token'}})

    assert entry['result'] == 'pong'
    assert introduced == []


def test_a_render_call_binds_new_children_whatever_was_submitted(card) -> None:
    # A host mounting a component calls render, which runs every slot's initializer.
    entry, _ = call(card, 'render', child_submissions(card, contact=VALID_CONTACT))

    assert 'html' in entry


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


def test_the_glue_object_types_are_named_on_glue() -> None:
    assert Glue.Form is FormGlue
    assert Glue.Model is ModelGlue
    assert Glue.QuerySet is QuerySetGlue
    assert Glue.Sequence is SequenceGlue
    assert (Glue.Operation, Glue.OperationKind) == (GlueOperation, GlueOperationKind)

    class Card(Component):
        template = 'glue_template_test.html'

        @Glue.child
        def contact(self) -> Glue.Form:
            return Glue.form(target=ContactPromoterForm(), access=self.access)

    assert Card.__dict__['contact'].__glue_options__.expected_type is FormGlue


def test_a_child_needs_a_glue_object_return_type() -> None:
    with pytest.raises(TypeError, match='return annotation'):
        class Untyped(Component):
            template = 'glue_template_test.html'

            @Glue.child
            def contact(self):
                return Glue.form(target=ContactPromoterForm())


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault('widget', MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data: Any, initial: Any = None) -> list[Any]:
        single_clean = super().clean
        if isinstance(data, (list, tuple)):
            return [single_clean(item, initial) for item in data]
        return [single_clean(data, initial)] if data else []


class SupportingPaperForm(forms.Form):
    title = forms.CharField()
    attachments = MultipleFileField(required=False)


class RowUploadForm(forms.Form):
    note = forms.CharField()
    proof = forms.FileField(required=False)


class RowUploadFormSet(Glue.FormSet):
    form_class = RowUploadForm
    min_num = 1


class UploadCardComponent(Component):
    template = 'glue_template_test.html'

    @Glue.child
    def paper(self) -> Glue.Form:
        return Glue.form(target=SupportingPaperForm(), access=self.access)

    @Glue.child
    def rows(self) -> Glue.FormSet:
        return RowUploadFormSet(initial=[{'note': 'First'}], access=self.access)

    @Glue.attr(required_access=Glue.Access.ADD, skip_rerender=True)
    def submit(self) -> dict[str, Any]:
        assert all_valid([self.paper, self.rows])
        return {
            'paper_files': [file.name for file in self.paper.cleaned_data['attachments']],
            'row_files': [row['proof'].name if row.get('proof') else None for row in self.rows.cleaned_data],
        }


def test_files_uploaded_for_child_forms_and_formset_rows_bind_under_their_slot_prefixes(mock_request) -> None:
    upload_card = Glue.object(mock_request, UploadCardComponent(access=Glue.Access.ADD))
    tokens = tokens_by_address(upload_card)
    rows_token = tokens[upload_card.policy.children['rows']]
    [row_key] = GluePolicy.from_token(rows_token).children
    row_address = GluePolicy.from_token(rows_token).children[row_key]

    submissions = {
        'paper': {'policy_token': tokens[upload_card.policy.children['paper']], 'updates': {'title': 'Accrual'}},
        'rows': {
            'policy_token': rows_token,
            'updates': {},
            'forms': {
                row_key: {'policy_token': tokens[row_address], 'updates': {'note': 'Line 1'}},
            },
        },
    }
    context = call_context(upload_card, 'submit').model_copy(update={'child_submissions': submissions})
    context.request._files = MultiValueDict({
        'child_submissions.paper.attachments': [
            SimpleUploadedFile('workpaper.pdf', b'%PDF-1.4', content_type='application/pdf'),
            SimpleUploadedFile('schedule.csv', b'a,b\n1,2\n', content_type='text/csv'),
        ],
        f'child_submissions.rows.forms.{row_key}.proof': [
            SimpleUploadedFile('receipt.txt', b'paid', content_type='text/plain'),
        ],
        'child_submissions.other.attachments': [
            SimpleUploadedFile('stranger.pdf', b'%PDF', content_type='application/pdf'),
        ],
    })

    rebuilt = UploadCardComponent.from_attribute_call_resolver_context(context)
    entry, _ = rebuilt.process_attribute_call(context)

    assert entry['result'] == {
        'paper_files': ['workpaper.pdf', 'schedule.csv'],
        'row_files': ['receipt.txt'],
    }


@pytest.mark.django_db
def test_files_uploaded_for_child_model_bind_under_its_slot_prefix(mock_request, tmp_path, settings) -> None:
    from test_project.gorilla.models import Gorilla  # noqa: PLC0415

    settings.MEDIA_ROOT = str(tmp_path)
    gif = b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
    gorilla = Gorilla.objects.create(name='Koko', age=10, weight=100.0, height=1.5)

    class GorillaCardComponent(Component):
        template = 'glue_template_test.html'

        @Glue.child
        def fighter(self) -> Glue.Model:
            return Glue.model(
                target=gorilla,
                fields=['name', 'profile_photo'],
                access=self.access,
            )

        @Glue.attr(required_access=Glue.Access.CHANGE, skip_rerender=True)
        def save_fighter(self) -> dict[str, Any]:
            return self.fighter.save()

    card = Glue.object(mock_request, GorillaCardComponent(access=Glue.Access.CHANGE))
    fighter_token = tokens_by_address(card)[card.policy.children['fighter']]
    context = call_context(card, 'save_fighter').model_copy(update={
        'child_submissions': {'fighter': {'policy_token': fighter_token, 'updates': {'name': 'Koko Updated'}}},
    })
    context.request._files = MultiValueDict({
        'child_submissions.fighter.profile_photo': [
            SimpleUploadedFile('portrait.gif', gif, content_type='image/gif'),
        ],
        'profile_photo': [
            SimpleUploadedFile('unscoped.gif', gif, content_type='image/gif'),
        ],
    })

    rebuilt = GorillaCardComponent.from_attribute_call_resolver_context(context)
    entry, _ = rebuilt.process_attribute_call(context)

    gorilla.refresh_from_db()
    assert entry['result']['success'] is True
    assert gorilla.name == 'Koko Updated'
    assert gorilla.profile_photo.name.startswith('gorilla_photos/portrait')
