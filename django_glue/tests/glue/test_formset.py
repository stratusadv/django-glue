from __future__ import annotations


from django import forms
from django.test import TestCase

from django_glue import Glue
from django_glue.exceptions import GlueFormSetMaxNumExceededError
from django_glue.glue.objects.django.formset import FormSetGlue
from django_glue.glue.policy import GluePolicy
from django_glue.glue.registry import glue_class_registry
from django_glue.resolver.attribute_call.context import AttributeCallRequestContext
from test_project.test_forms import ContactForm

from django_glue.tests.glue.test_objects import (
    glue_context,
    request_with_session,
    with_request,
)


class SampleContactFormSet(Glue.FormSet):
    """Module-level so ``get_attr_from_path_string`` can resolve it on reconstruction."""

    form_class = ContactForm
    min_num = 1
    max_num = 5

    def clean(self, form_list):
        return ['Test cross-form error.']


class FormSetGlueTestCase(TestCase):
    def test_attributes_expose_declared_attributes_and_keyed_forms(self):
        glue_object = with_request(FormSetGlue(ContactForm, **glue_context(name='contacts')))
        glue_object.append(key='1', initial={})

        self.assertIn('append', glue_object.attributes)
        self.assertIn('validate', glue_object.attributes)
        # Keyed children are addressed by their key, not a positional attribute.
        self.assertIn('1', glue_object.children)

    def test_identity_captures_formset_configuration(self):
        glue_object = FormSetGlue(
            ContactForm,
            **glue_context(name='contacts'),
            min_num=1,
            max_num=5,
            can_delete=True,
        )

        identity = glue_object.get_identity()

        self.assertEqual(identity['form_class_path'], 'test_project.test_forms.ContactForm')
        self.assertEqual(identity['min_num'], 1)
        self.assertEqual(identity['max_num'], 5)
        self.assertTrue(identity['can_delete'])

    def test_requires_a_form_class(self):
        with self.assertRaises(ValueError):
            FormSetGlue(**glue_context(name='contacts'))

    def test_append_returns_a_bound_form_glue_with_initial_values(self):
        glue_object = with_request(FormSetGlue(ContactForm, **glue_context(name='contacts')))

        appended = glue_object.append(key='1', initial={'name': 'Ada'})

        self.assertEqual(appended.state['name']['value'], 'Ada')
        self.assertEqual(glue_object.get_keyed_items(), [('1', appended)])

    def test_append_rejects_when_max_num_is_reached(self):
        glue_object = with_request(FormSetGlue(
            ContactForm, **glue_context(name='contacts'), max_num=2,
        ))
        glue_object.append(key='1', initial={})
        glue_object.append(key='2', initial={})

        with self.assertRaises(GlueFormSetMaxNumExceededError) as caught:
            glue_object.append(key='3', initial={})

        self.assertEqual(caught.exception.current_count, 2)
        self.assertEqual(caught.exception.max_num, 2)
        self.assertEqual(len(glue_object.get_keyed_items()), 2)

    def test_append_is_unbounded_when_max_num_is_none(self):
        glue_object = with_request(FormSetGlue(ContactForm, **glue_context(name='contacts')))

        for key in ('1', '2', '3'):
            glue_object.append(key=key, initial={})

        self.assertEqual(len(glue_object.get_keyed_items()), 3)

    def test_append_attribute_call_introduces_the_new_child_as_an_entry(self):
        glue_object = with_request(FormSetGlue(ContactForm, **glue_context(name='contacts')))
        policy = glue_object.policy
        reconstructed = FormSetGlue._reconstruct_from_policy(policy)
        reconstructed.request = request_with_session()
        context = AttributeCallRequestContext.model_construct(
            request=reconstructed.request,
            target_glue_policy=policy,
            target_glue_updates={},
            target_attribute_name='append',
            target_attribute_call_kwargs={'key': '1', 'initial': {'name': 'Ada'}},
        )

        entry, introduced = reconstructed.process_attribute_call(context)

        self.assertEqual(len(introduced), 1)
        introduction = introduced[0]
        child_policy = GluePolicy.from_token(introduction['policy_token'])
        self.assertEqual(child_policy.name, 'contacts.1')
        self.assertEqual(child_policy.namespace, 'form')
        self.assertEqual(child_policy.state_snapshot['name'], 'Ada')
        self.assertEqual(introduction['address'], entry['result'])
        successor = GluePolicy.from_token(entry['policy_token'])
        self.assertEqual(successor.children, {'1': introduction['address']})

    def test_attribute_call_without_child_changes_omits_introductions(self):
        glue_object = with_request(FormSetGlue(ContactForm, **glue_context(name='contacts')))
        policy = glue_object.policy
        reconstructed = FormSetGlue._reconstruct_from_policy(policy)
        reconstructed.request = request_with_session()
        context = AttributeCallRequestContext.model_construct(
            request=reconstructed.request,
            target_glue_policy=policy,
            target_glue_updates={},
            target_attribute_name='validate',
            target_attribute_call_kwargs={},
        )

        entry, introduced = reconstructed.process_attribute_call(context)

        self.assertEqual(introduced, [])
        self.assertNotIn('policy_token', entry)
        self.assertTrue(entry['result']['valid'])

    def test_collection_starts_empty(self):
        glue_object = with_request(FormSetGlue(ContactForm, **glue_context(name='contacts')))

        self.assertEqual(glue_object.get_keyed_items(), [])

    def test_validate_reports_invalid_when_required_fields_are_missing(self):
        glue_object = with_request(FormSetGlue(ContactForm, **glue_context(name='contacts')))
        glue_object.append(key='1', initial={})

        result = glue_object.validate()

        self.assertFalse(result['valid'])
        self.assertEqual(len(result['form_list']), 1)

    def test_load_client_state_rematerializes_keyed_forms(self):
        glue_object = with_request(FormSetGlue(ContactForm, **glue_context(name='contacts')))

        glue_object._load_client_state({'forms': {
            '1': {
                'name': 'Ada',
                'email': 'ada@example.com',
                'message': 'Hello',
                'priority': 'low',
            },
        }})

        self.assertEqual(len(glue_object._forms), 1)
        key, form_glue = glue_object._forms[0]
        self.assertEqual(key, '1')
        self.assertTrue(form_glue.form.is_bound)

    def test_validate_reports_valid_when_data_is_bound_and_complete(self):
        glue_object = with_request(FormSetGlue(ContactForm, **glue_context(name='contacts')))
        glue_object._load_client_state({'forms': {
            '1': {
                'name': 'Ada',
                'email': 'ada@example.com',
                'message': 'Hello',
                'priority': 'low',
            },
        }})

        result = glue_object.validate()

        self.assertTrue(result['valid'])

    def test_clean_receives_django_forms_not_form_glues(self):
        seen: list[forms.BaseForm] = []

        class ContactFormSet(Glue.FormSet):
            form_class = ContactForm
            min_num = 1
            max_num = 5

            def clean(self, form_list):
                seen.extend(form_list)
                return []

        glue_object = with_request(ContactFormSet(**glue_context(name='contacts')))
        glue_object.append(key='1', initial={'name': 'Ada', 'email': 'ada@example.com'})

        glue_object.validate()

        self.assertEqual(len(seen), 1)
        self.assertIsInstance(seen[0], forms.BaseForm)

    def test_clean_errors_make_validation_invalid(self):
        class ContactFormSet(Glue.FormSet):
            form_class = ContactForm
            min_num = 1
            max_num = 5

            def clean(self, form_list):
                return ['Cross-form constraint failed.']

        glue_object = with_request(ContactFormSet(**glue_context(name='contacts')))
        glue_object.append(key='1', initial={'name': 'Ada', 'email': 'ada@example.com'})

        result = glue_object.validate()

        self.assertFalse(result['valid'])
        self.assertEqual(result['non_form_errors'], ['Cross-form constraint failed.'])

    def test_validate_reports_a_min_num_violation(self):
        glue_object = with_request(FormSetGlue(
            ContactForm, **glue_context(name='contacts'), min_num=2,
        ))

        result = glue_object.validate()

        self.assertFalse(result['valid'])
        self.assertEqual(result['non_form_errors'], ['Please submit at least 2 form(s).'])

    def test_validate_reports_a_max_num_violation(self):
        glue_object = with_request(FormSetGlue(
            ContactForm, **glue_context(name='contacts'), min_num=0, max_num=1,
        ))
        glue_object._load_client_state({'forms': {
            '1': {
                'name': 'Ada',
                'email': 'ada@example.com',
                'message': 'Hello',
                'priority': 'low',
            },
            '2': {
                'name': 'Bee',
                'email': 'bee@example.com',
                'message': 'Hi',
                'priority': 'low',
            },
        }})

        result = glue_object.validate()

        self.assertFalse(result['valid'])
        self.assertEqual(result['non_form_errors'], ['Please submit at most 1 form(s).'])

    def test_validate_passes_cardinality_when_within_bounds(self):
        glue_object = with_request(FormSetGlue(
            ContactForm, **glue_context(name='contacts'), min_num=1, max_num=2,
        ))
        glue_object._load_client_state({'forms': {
            '1': {
                'name': 'Ada',
                'email': 'ada@example.com',
                'message': 'Hello',
                'priority': 'low',
            },
        }})

        result = glue_object.validate()

        self.assertTrue(result['valid'])
        self.assertEqual(result['non_form_errors'], [])

    def test_reconstruct_from_policy_rebuilds_an_equivalent_formset(self):
        glue_object = with_request(FormSetGlue(
            ContactForm,
            **glue_context(name='contacts'),
            min_num=1,
            max_num=5,
            can_delete=True,
        ))
        policy = glue_object.policy

        resolved = FormSetGlue._reconstruct_from_policy(policy)

        self.assertEqual(resolved.form_class, ContactForm)
        self.assertEqual(resolved.min_num, 1)
        self.assertEqual(resolved.max_num, 5)
        self.assertTrue(resolved.can_delete)

    def test_custom_formset_clean_survives_reconstruct_round_trip(self):
        glue_object = with_request(SampleContactFormSet(**glue_context(name='contacts')))
        policy = glue_object.policy

        resolved = FormSetGlue._reconstruct_from_policy(policy)

        self.assertIsInstance(resolved, SampleContactFormSet)
        self.assertEqual(resolved.form_class, ContactForm)
        self.assertEqual(resolved.clean([ContactForm()]), ['Test cross-form error.'])

    def test_glue_formset_shortcut_from_form_class(self):
        request = with_request(FormSetGlue(ContactForm, **glue_context(name='noop'))).request

        glue_object = Glue.formset(
            target=ContactForm,
            request=request,
            unique_name='contacts',
            access=Glue.Access.CHANGE,
            min_num=2,
            max_num=10,
        )

        self.assertIsInstance(glue_object, FormSetGlue)
        self.assertEqual(glue_object.name, 'contacts')
        self.assertEqual(glue_object.form_class, ContactForm)
        self.assertEqual(glue_object.min_num, 2)
        self.assertEqual(glue_object.max_num, 10)

    def test_glue_formset_shortcut_from_custom_formset_class(self):
        class ContactFormSet(Glue.FormSet):
            form_class = ContactForm
            min_num = 1
            max_num = 5

        request = with_request(FormSetGlue(ContactForm, **glue_context(name='noop'))).request

        glue_object = Glue.formset(
            target=ContactFormSet,
            request=request,
            unique_name='contacts',
            access=Glue.Access.CHANGE,
            max_num=8,
        )

        self.assertIsInstance(glue_object, ContactFormSet)
        self.assertEqual(glue_object.form_class, ContactForm)
        self.assertEqual(glue_object.min_num, 1)
        self.assertEqual(glue_object.max_num, 8)

    def test_formset_namespace_is_registered_in_glue_class_registry(self):
        # The registry is what GlueAttributeCallResolver uses to
        # reconstruct a glue object from an incoming request's policy
        # namespace -- a class that works standalone but isn't registered
        # here still 500s on every real callable-attribute request against it.
        self.assertIs(glue_class_registry.get_glue_class('formSet'), FormSetGlue)
