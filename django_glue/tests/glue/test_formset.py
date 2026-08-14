from __future__ import annotations

from django.forms import BaseFormSet, formset_factory
from django.test import TestCase

from django_glue import Glue
from django_glue.glue.objects.django.formset import FormSetGlue
from django_glue.glue.registry import glue_class_registry
from test_project.test_forms import ContactForm

from django_glue.tests.glue.test_adapters import glue_context, with_request


def build_formset(**kwargs):
    formset_class = formset_factory(
        ContactForm,
        formset=BaseFormSet,
        extra=0,
        min_num=1,
        validate_min=True,
        max_num=5,
        validate_max=True,
        can_delete=True,
    )
    return formset_class(**kwargs)


class FormSetGlueTestCase(TestCase):
    def test_attributes_expose_declared_attributes_and_nested_forms(self):
        glue_object = with_request(FormSetGlue(build_formset(), **glue_context(name='contacts')))

        self.assertIn('append', glue_object.attributes)
        self.assertIn('validate', glue_object.attributes)
        self.assertIn('load_state', glue_object.attributes)
        self.assertIn('form_list.0', glue_object.attributes)

    def test_identity_captures_formset_configuration(self):
        glue_object = FormSetGlue(build_formset(), **glue_context(name='contacts'))

        identity = glue_object.get_identity()

        self.assertEqual(identity['form_class_path'], 'test_project.test_forms.ContactForm')
        self.assertEqual(identity['min_num'], 1)
        self.assertEqual(identity['max_num'], 5)
        self.assertTrue(identity['can_delete'])

    def test_append_returns_a_bound_form_glue_with_initial_values(self):
        glue_object = with_request(FormSetGlue(build_formset(), **glue_context(name='contacts')))

        appended = glue_object.append(key='1', initial={'name': 'Ada'})

        self.assertEqual(appended.state['name']['value'], 'Ada')

    def test_validate_reports_invalid_when_required_fields_are_missing(self):
        glue_object = with_request(FormSetGlue(build_formset(), **glue_context(name='contacts')))

        result = glue_object.validate()

        self.assertFalse(result['valid'])
        self.assertEqual(len(result['form_list']), 1)

    def test_load_client_state_binds_form_list(self):
        glue_object = with_request(FormSetGlue(build_formset(), **glue_context(name='contacts')))

        glue_object._load_client_state({'form_list': [{
            'name': {'value': 'Ada'},
            'email': {'value': 'ada@example.com'},
            'message': {'value': 'Hello'},
            'priority': {'value': 'low'},
        }]})

        self.assertEqual(len(glue_object.formset.forms), 1)
        self.assertTrue(glue_object.formset.is_valid())

    def test_validate_reports_valid_when_data_is_bound_and_complete(self):
        data = {
            'form-TOTAL_FORMS': '1',
            'form-INITIAL_FORMS': '0',
            'form-MIN_NUM_FORMS': '1',
            'form-MAX_NUM_FORMS': '5',
            'form-0-name': 'Ada',
            'form-0-email': 'ada@example.com',
            'form-0-message': 'Hello',
            'form-0-priority': 'low',
        }
        glue_object = with_request(FormSetGlue(build_formset(data=data), **glue_context(name='contacts')))

        result = glue_object.validate()

        self.assertTrue(result['valid'])

    def test_reconstruct_from_policy_rebuilds_an_equivalent_formset(self):
        glue_object = with_request(FormSetGlue(build_formset(), **glue_context(name='contacts')))
        policy = glue_object.policy

        resolved = FormSetGlue._reconstruct_from_policy(policy)

        self.assertEqual(resolved.formset.prefix, glue_object.formset.prefix)
        self.assertEqual(resolved.formset.min_num, glue_object.formset.min_num)
        self.assertTrue(resolved.formset.can_delete)

    def test_glue_formset_shortcut_registers_the_object(self):
        request = with_request(FormSetGlue(build_formset(), **glue_context(name='noop'))).request

        glue_object = Glue.formset(request, 'contacts', build_formset(), Glue.Access.CHANGE)

        self.assertIsInstance(glue_object, FormSetGlue)
        self.assertEqual(glue_object.name, 'contacts')

    def test_formset_namespace_is_registered_in_glue_class_registry(self):
        # The registry is what GlueAttributeCallResolver uses to
        # reconstruct a glue object from an incoming request's policy
        # namespace (django_glue/resolver/attribute_call/resolver.py) --
        # a class that works standalone but isn't registered here still
        # 500s on every real callable-attribute request against it.
        self.assertIs(glue_class_registry.get_glue_class('formSet'), FormSetGlue)
