"""
Glue offers a form's default save only to a model form whose ``Meta`` sets
``glue_default_save = True`` (ADR 040).
"""

from __future__ import annotations

import json

from django import forms
from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase

from django_glue.access import GlueAccess
from django_glue.exceptions import GlueMissingAttributeError
from django_glue.glue.objects.django.form.object import FormGlue
from django_glue.glue.objects.django.formset import FormSetGlue
from django_glue.tests.glue.test_add_creation import _AttributeRequestMixin
from django_glue.tests.glue.test_formset import call_across_requests, row_tokens
from django_glue.tests.glue.test_objects import glue_context, with_request
from test_project.gorilla.models import Gorilla

GORILLA_VALUES = {'name': 'Filo', 'age': 5, 'weight': 200.0, 'height': 1.8}


class GorillaValuesForm(forms.ModelForm):
    """Module-level so a rebuilt formset can import it."""

    class Meta:
        model = Gorilla
        fields = ['name', 'age', 'weight', 'height']


class GorillaDefaultSaveForm(forms.ModelForm):
    class Meta:
        model = Gorilla
        fields = ['name', 'age', 'weight', 'height']
        glue_default_save = True


class InheritingDefaultSaveForm(GorillaDefaultSaveForm):
    class Meta(GorillaDefaultSaveForm.Meta):
        fields = ['name']


class ReplacingMetaForm(GorillaDefaultSaveForm):
    class Meta:
        model = Gorilla
        fields = ['name']


class PlainFormOptingIn(forms.Form):
    name = forms.CharField()

    class Meta:
        glue_default_save = True


class StringOptionForm(forms.ModelForm):
    class Meta:
        model = Gorilla
        fields = ['name']
        glue_default_save = 'yes'


def callables(glue_object: FormGlue | FormSetGlue) -> set[str]:
    return set(glue_object.get_static_data().get('callables', {}))


class FormGlueDefaultSaveTestCase(_AttributeRequestMixin, TestCase):
    def glued(self, form_class: type[forms.BaseForm]) -> FormGlue:
        glue_object = FormGlue(
            form_class(instance=Gorilla()),
            name='gorilla_form',
            access=GlueAccess.ADD,
        )
        glue_object.request = self.request_context()
        return glue_object

    def request_context(self) -> object:
        return type('Request', (), {'session': self.session, 'FILES': {}, 'path_info': '/'})()

    def test_a_model_form_that_does_not_opt_in_is_not_offered_save(self) -> None:
        glue_object = self.glued(GorillaValuesForm)

        self.assertNotIn('save', glue_object.policy.attributes)
        self.assertNotIn('save', callables(glue_object))
        self.assertIn('validate', callables(glue_object))

    def test_a_save_call_on_a_form_that_does_not_opt_in_is_refused(self) -> None:
        glue_object = self.glued(GorillaValuesForm)

        response = self.call('gorilla_form', glue_object.policy, 'save', updates=GORILLA_VALUES)

        error = json.loads(response.content)['objects'][0]['error']
        self.assertEqual(error['code'], 'missing_attribute')
        self.assertEqual(error['details']['attribute'], 'save')
        self.assertFalse(Gorilla.objects.filter(name='Filo').exists())

    def test_validate_still_works_without_the_opt_in(self) -> None:
        glue_object = self.glued(GorillaValuesForm)

        response = self.call('gorilla_form', glue_object.policy, 'validate', updates=GORILLA_VALUES)

        self.assertTrue(json.loads(response.content)['objects'][0]['result']['valid'])

    def test_a_model_form_that_opts_in_is_offered_save_and_saves(self) -> None:
        glue_object = self.glued(GorillaDefaultSaveForm)

        self.assertIn('save', callables(glue_object))

        response = self.call('gorilla_form', glue_object.policy, 'save', updates=GORILLA_VALUES)

        self.assertTrue(json.loads(response.content)['objects'][0]['result']['valid'])
        self.assertTrue(Gorilla.objects.filter(name='Filo').exists())

    def test_the_option_is_inherited_as_metas_other_options_are(self) -> None:
        self.assertIn('save', callables(self.glued(InheritingDefaultSaveForm)))
        self.assertNotIn('save', callables(self.glued(ReplacingMetaForm)))

    def test_a_form_without_a_save_that_opts_in_is_refused_when_glued(self) -> None:
        with self.assertRaisesMessage(ImproperlyConfigured, 'has no save()'):
            FormGlue(PlainFormOptingIn(), **glue_context(name='plain'))

    def test_an_option_that_is_not_a_bool_is_refused_when_glued(self) -> None:
        with self.assertRaisesMessage(ImproperlyConfigured, 'must be True or False'):
            FormGlue(StringOptionForm(), **glue_context(name='string'))


class FormSetGlueDefaultSaveTestCase(TestCase):
    def glued(self, form_class: type[forms.BaseForm]) -> FormSetGlue:
        return with_request(FormSetGlue(form_class, extra=1, **glue_context(name='gorillas')))

    def test_a_formset_whose_rows_do_not_opt_in_offers_no_save_on_itself_or_its_rows(self) -> None:
        formset = self.glued(GorillaValuesForm)
        [row] = [form for _, form in formset._forms]

        self.assertNotIn('save', callables(formset))
        self.assertNotIn('save', callables(row))
        self.assertTrue({'append', 'pop', 'validate'} <= callables(formset))

    def test_a_call_to_save_on_such_a_formset_is_refused_and_writes_nothing(self) -> None:
        formset = self.glued(GorillaValuesForm)
        [token] = row_tokens(formset).values()

        with self.assertRaisesMessage(GlueMissingAttributeError, "Attribute 'save' not found"):
            call_across_requests(formset.policy, 'save', {
                '__submitted_forms': {'0': {'policy_token': token, 'updates': GORILLA_VALUES}},
            })
        self.assertFalse(Gorilla.objects.filter(name='Filo').exists())

    def test_server_code_may_still_save_such_a_formset(self) -> None:
        formset = self.glued(GorillaValuesForm)
        [(_, row)] = formset._forms
        row._stage_form_attribute_value('name', 'Filo')
        for name in ('age', 'weight', 'height'):
            row._stage_form_attribute_value(name, GORILLA_VALUES[name])

        self.assertEqual(formset.save(), {'valid': True})
        self.assertTrue(Gorilla.objects.filter(name='Filo').exists())

    def test_a_formset_whose_rows_opt_in_offers_save(self) -> None:
        formset = self.glued(GorillaDefaultSaveForm)
        [row] = [form for _, form in formset._forms]

        self.assertIn('save', callables(formset))
        self.assertIn('save', callables(row))

    def test_a_formset_with_no_rows_still_refuses_a_form_without_a_save_that_opts_in(self) -> None:
        with self.assertRaisesMessage(ImproperlyConfigured, 'has no save()'):
            FormSetGlue(PlainFormOptingIn, **glue_context(name='plain'))
