from __future__ import annotations

from typing import Any

from django import forms

from django_glue import Glue
from django_glue.glue.objects.django.form.object import FormGlue


class InvitedAccountForm(forms.Form):
    email = forms.EmailField(disabled=True)
    name = forms.CharField()


class ScopedForm(forms.Form):
    name = forms.CharField()

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.scope = self.initial['scope']


def glued(request, form: forms.Form) -> FormGlue:
    return Glue.form(request, unique_name='form', target=form, access=Glue.Access.CHANGE)


def test_a_disabled_field_validates_with_the_initial_the_form_was_given(mock_request) -> None:
    form = glued(mock_request, InvitedAccountForm(initial={'email': 'dana@example.com'}))
    form._stage_form_attribute_value('name', 'Dana')

    assert form.is_valid()
    assert form.cleaned_data['email'] == 'dana@example.com'


def test_a_form_validates_with_the_initial_its_init_reads(mock_request) -> None:
    form = glued(mock_request, ScopedForm(initial={'scope': 12}))
    form._stage_form_attribute_value('name', 'Dana')

    assert form.is_valid()
    assert form.bound_form.scope == 12


def test_a_form_rebuilt_from_its_token_validates_with_its_initial(mock_request) -> None:
    rebuilt = FormGlue._reconstruct_from_policy(glued(mock_request, ScopedForm(initial={'scope': 12})).policy)
    rebuilt._stage_form_attribute_value('name', 'Dana')

    assert rebuilt.is_valid()
    assert rebuilt.bound_form.scope == 12


def test_a_form_left_as_it_was_given_has_not_changed(mock_request) -> None:
    form = glued(mock_request, InvitedAccountForm(initial={'email': 'dana@example.com', 'name': 'Dana'}))

    assert form.is_valid()
    assert not form.bound_form.has_changed()
