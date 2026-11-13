"""
A formset's ``form_kwargs`` reach every row form it builds or rebuilds, and its
``get_form_kwargs()`` may add values derived once per request (ADR 041).
"""

from __future__ import annotations

from functools import cached_property
from typing import Any

from django import forms
from django.core.validators import MaxValueValidator
from django.test import TestCase

from django_glue import Glue
from django_glue.glue.objects.django.form.object import FormGlue
from django_glue.glue.objects.django.formset import FormSetGlue
from django_glue.glue.policy import GluePolicy
from django_glue.tests.glue.test_formset import call_across_requests, row_tokens
from django_glue.tests.glue.test_objects import glue_context, with_request
from test_project.gorilla.models import Gorilla


class CappedAgeForm(forms.Form):
    """A row form whose age limit is a constructor argument, as a scoped choice would be."""

    name = forms.CharField()
    age = forms.IntegerField()

    def __init__(
        self,
        *args: Any,
        max_age: int,
        reserved_names: frozenset[str] = frozenset(),
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.max_age = max_age
        self.reserved_names = reserved_names
        self.fields['age'].validators.append(MaxValueValidator(max_age))

    def clean_name(self) -> str:
        name = self.cleaned_data['name']
        if name in self.reserved_names:
            msg = 'That name is taken.'
            raise forms.ValidationError(msg)
        return name


class ReservedNamesFormSet(Glue.FormSet):
    """Derives one value from its signed kwargs, once, and hands it to every row."""

    form_class = CappedAgeForm
    derivations = 0

    @cached_property
    def reserved_names(self) -> frozenset[str]:
        ReservedNamesFormSet.derivations += 1
        older = Gorilla.objects.filter(age__gt=self.form_kwargs['max_age'])
        return frozenset(older.values_list('name', flat=True))

    def get_form_kwargs(self) -> dict[str, Any]:
        return {**super().get_form_kwargs(), 'reserved_names': self.reserved_names}


def row_forms(formset: FormSetGlue) -> list[forms.BaseForm]:
    return [row.form for _, row in formset._forms]


class FormSetFormKwargsTestCase(TestCase):
    def glued(self, formset_class: type[FormSetGlue] = FormSetGlue, **kwargs: Any) -> FormSetGlue:
        return with_request(formset_class(
            CappedAgeForm,
            form_kwargs={'max_age': 10},
            initial=[{'name': 'Koko'}],
            extra=1,
            **glue_context(name='gorillas', access=Glue.Access.ADD),
            **kwargs,
        ))

    def test_every_row_the_formset_builds_gets_the_kwargs(self) -> None:
        formset = self.glued()
        formset.append('2')

        assert [form.max_age for form in row_forms(formset)] == [10, 10, 10]

    def test_the_kwargs_are_signed_with_the_formset_and_each_row(self) -> None:
        formset = self.glued()

        assert formset.policy.identity['form_kwargs'] == {'max_age': 10}
        for token in row_tokens(formset).values():
            assert GluePolicy.from_token(token).identity['form_kwargs'] == {'max_age': 10}

    def test_rows_rebuilt_by_the_formset_get_the_kwargs(self) -> None:
        formset = self.glued()
        submitted = {
            key: {'policy_token': token, 'updates': {'name': 'Koko', 'age': 11}}
            for key, token in row_tokens(formset).items()
        }

        entry, _ = call_across_requests(
            formset.policy,
            'validate',
            {'__submitted_forms': submitted},
        )

        assert entry['result']['valid'] is False

    def test_a_row_rebuilt_on_its_own_gets_the_signed_kwargs(self) -> None:
        formset = self.glued()
        [token, *_] = row_tokens(formset).values()

        row = FormGlue._reconstruct_from_policy(GluePolicy.from_token(token))

        assert row.form.max_age == 10
        assert row.form_kwargs == {'max_age': 10}

    def test_derived_kwargs_are_made_once_and_shared_by_every_row(self) -> None:
        Gorilla.objects.create(name='Silverback', age=30)
        ReservedNamesFormSet.derivations = 0

        formset = self.glued(ReservedNamesFormSet)
        formset.append('2')

        [first, *others] = row_forms(formset)
        assert first.reserved_names == frozenset({'Silverback'})
        assert all(form.reserved_names is first.reserved_names for form in others)
        assert ReservedNamesFormSet.derivations == 1

    def test_rows_validated_in_a_later_request_get_the_derived_kwargs_made_once(self) -> None:
        Gorilla.objects.create(name='Silverback', age=30)
        formset = self.glued(ReservedNamesFormSet)
        submitted = {
            key: {'policy_token': token, 'updates': {'name': 'Silverback', 'age': 5}}
            for key, token in row_tokens(formset).items()
        }
        ReservedNamesFormSet.derivations = 0

        entry, _ = call_across_requests(
            formset.policy,
            'validate',
            {'__submitted_forms': submitted},
        )

        assert entry['result']['valid'] is False
        assert ReservedNamesFormSet.derivations == 1

    def test_derived_kwargs_are_not_signed(self) -> None:
        formset = self.glued(ReservedNamesFormSet)

        assert formset.policy.identity['form_kwargs'] == {'max_age': 10}

    def test_kwargs_that_cannot_be_signed_are_refused(self) -> None:
        gorilla = Gorilla.objects.create(name='Koko')

        with self.assertRaisesMessage(TypeError, 'pass a related record as its primary key'):
            FormSetGlue(
                CappedAgeForm,
                form_kwargs={'gorilla': gorilla},
                **glue_context(name='gorillas'),
            )
