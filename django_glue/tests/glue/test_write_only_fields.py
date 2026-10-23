from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest
from django import forms

from django_glue import Glue
from django_glue.encoders import GlueResponseJSONEncoder
from django_glue.glue.objects.django.form.object import FormGlue
from django_glue.glue.policy import GluePolicy
from django_glue.tests.glue.test_callable_parameters import call_context

if TYPE_CHECKING:
    from django.http import HttpRequest


SECRET = 'mulch-season-2026'  # noqa: S105


class AccountForm(forms.Form):
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)
    pin = forms.CharField(widget=forms.PasswordInput(render_value=True), required=False)


def account_form(
    request: HttpRequest,
    access: Glue.Access = Glue.Access.CHANGE,
    **initial: Any,
) -> FormGlue:
    return Glue.form(request, target=AccountForm(initial=initial), access=access)


def validate(form: FormGlue, updates: dict[str, Any]) -> dict[str, Any]:
    context = call_context(form, 'validate', updates=updates)
    rebuilt = FormGlue.from_attribute_call_resolver_context(context)
    entry, _ = rebuilt.process_attribute_call(context)
    return entry


def wire(entry: dict[str, Any]) -> str:
    """The entry as the browser can read it: a token is encoded, not encrypted."""
    decoded = dict(entry)
    if 'policy_token' in entry:
        decoded['policy_token'] = GluePolicy.from_token(entry['policy_token']).model_dump()
    return json.dumps(decoded, cls=GlueResponseJSONEncoder)


def test_only_a_password_input_hiding_its_value_is_write_only(mock_request: HttpRequest) -> None:
    fields = account_form(mock_request).get_static_data()['fields']

    assert fields['password']['write_only'] is True
    assert fields['password']['editable'] is True
    assert 'write_only' not in fields['pin']
    assert 'write_only' not in fields['email']


def test_introduction_signs_and_emits_no_password(mock_request: HttpRequest) -> None:
    form = account_form(mock_request, email='dana@northwind.example', password=SECRET)

    assert 'password' not in form.policy.state_snapshot
    assert 'password' not in form.policy.identity['initial']
    assert form.policy.state_snapshot['email'] == 'dana@northwind.example'
    assert SECRET not in wire(form.entry.model_dump())


def test_a_view_only_password_field_reads_as_nothing(mock_request: HttpRequest) -> None:
    form = account_form(mock_request, access=Glue.Access.VIEW, password=SECRET)

    computed = form.get_computed_data(include_all=True)

    assert computed['password'] is None
    assert SECRET not in wire(form.entry.model_dump())


def test_a_call_validates_the_password_and_never_returns_it(mock_request: HttpRequest) -> None:
    form = account_form(mock_request)

    entry = validate(form, {'email': 'dana@northwind.example', 'password': SECRET})

    assert entry['result']['valid'] is True
    assert SECRET not in wire(entry)
    successor = form.policy.from_token(entry['policy_token'])
    assert 'password' not in successor.state_snapshot
    assert successor.state_snapshot['email'] == 'dana@northwind.example'


def test_a_failed_call_returns_errors_but_not_the_password(mock_request: HttpRequest) -> None:
    form = account_form(mock_request)

    entry = validate(form, {'email': 'not-an-email', 'password': SECRET})

    assert entry['result']['valid'] is False
    assert entry['computed_data']['fields']['email']['errors']
    assert entry['computed_data']['fields']['password']['errors'] == []
    assert SECRET not in wire(entry)


def test_a_call_without_the_password_update_finds_it_missing(mock_request: HttpRequest) -> None:
    form = account_form(mock_request)
    first = validate(form, {'email': 'dana@northwind.example', 'password': SECRET})
    form.policy = form.policy.from_token(first['policy_token'])

    entry = validate(form, {})

    assert entry['result']['valid'] is False
    assert entry['computed_data']['fields']['password']['errors']
    assert 'email' not in entry['result']['errors']


def test_a_password_that_renders_its_value_stays_retained_state(mock_request: HttpRequest) -> None:
    form = account_form(mock_request)

    entry = validate(form, {'email': 'dana@northwind.example', 'password': SECRET, 'pin': '4821'})

    assert form.policy.from_token(entry['policy_token']).state_snapshot['pin'] == '4821'


def test_a_call_carrying_a_password_marks_its_body_sensitive(mock_request: HttpRequest) -> None:
    form = account_form(mock_request)
    mock_request.sensitive_post_parameters = ['note']

    validate(form, {'email': 'dana@northwind.example', 'password': SECRET})

    assert mock_request.sensitive_post_parameters == ['note', 'objects']


def test_a_call_without_a_password_marks_nothing_sensitive(mock_request: HttpRequest) -> None:
    form = account_form(mock_request)

    validate(form, {'email': 'dana@northwind.example'})

    assert not hasattr(mock_request, 'sensitive_post_parameters')


@pytest.mark.parametrize('already', ['__ALL__', ['objects']])
def test_an_already_sensitive_call_is_left_as_it_is(
    mock_request: HttpRequest,
    already: str | list[str],
) -> None:
    form = account_form(mock_request)
    mock_request.sensitive_post_parameters = already

    validate(form, {'email': 'dana@northwind.example', 'password': SECRET})

    assert mock_request.sensitive_post_parameters == already
