"""
Tests for GlueFormProxy save() action.
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_project.settings')
django.setup()

from django.test import TestCase

from django_glue.access.access import GlueAccess
from django_glue.proxies.form.proxy import GlueFormProxy
from django_glue.exceptions import GlueAccessError
from django_glue import data_transfer_objects as dto
from test_project.test_forms import ContactForm


class GlueFormProxySaveTestCase(TestCase):
    """Tests for GlueFormProxy.save() action."""

    def test_save_returns_success_true_for_valid_data(self):
        """save() should return success=True for valid data."""
        form = ContactForm()
        proxy = GlueFormProxy(target=form, unique_name='contact_form', access=GlueAccess.CHANGE)
        action_data = dto.GlueActionRequestData(
            context_data={},
            post_data={
                'name': 'John Doe',
                'email': 'john@example.com',
                'message': 'Hello world',
                'priority': 'medium',
            },
        )
        result = proxy.save(action_data)

        self.assertTrue(result['success'])
        self.assertIsNone(result['errors'])

    def test_save_returns_success_false_for_invalid_data(self):
        """save() should return success=False for invalid data."""
        form = ContactForm()
        proxy = GlueFormProxy(target=form, unique_name='contact_form', access=GlueAccess.CHANGE)
        action_data = dto.GlueActionRequestData(
            context_data={},
            post_data={'name': '', 'email': 'invalid', 'message': '', 'priority': 'medium'},
        )
        result = proxy.save(action_data)

        self.assertFalse(result['success'])
        self.assertIn('name', result['errors'])

    def test_save_returns_cleaned_data_for_regular_form(self):
        """save() should return cleaned_data for regular Form."""
        form = ContactForm()
        proxy = GlueFormProxy(target=form, unique_name='contact_form', access=GlueAccess.CHANGE)
        action_data = dto.GlueActionRequestData(
            context_data={},
            post_data={
                'name': 'John Doe',
                'email': 'john@example.com',
                'message': 'Hello world',
                'priority': 'high',
            },
        )
        result = proxy.save(action_data)

        self.assertIn('cleaned_data', result)
        self.assertEqual(result['cleaned_data']['name'], 'John Doe')
        self.assertEqual(result['cleaned_data']['priority'], 'high')

    def test_save_requires_change_access(self):
        """save() should require CHANGE access."""
        form = ContactForm()
        proxy = GlueFormProxy(target=form, unique_name='contact_form', access=GlueAccess.VIEW)

        action_data = dto.GlueActionRequestData(context_data={}, post_data={'name': 'Test'})

        with self.assertRaises(GlueAccessError):
            proxy.process_action('save', action_data)

    def test_save_works_with_delete_access(self):
        """save() should work with DELETE access (cascading)."""
        form = ContactForm()
        proxy = GlueFormProxy(target=form, unique_name='contact_form', access=GlueAccess.DELETE)
        action_data = dto.GlueActionRequestData(
            context_data={},
            post_data={
                'name': 'John Doe',
                'email': 'john@example.com',
                'message': 'Hello world',
                'priority': 'medium',
            },
        )
        result = proxy.save(action_data)

        self.assertTrue(result['success'])


class GlueFormProxyFromRegistryDataTestCase(TestCase):
    """Tests for from_action_request_data class method."""

    def test_reconstructs_form_from_class_path(self):
        """Should reconstruct form from stored class path."""
        proxy = GlueFormProxy.from_action_request_data(
            form_class_path='test_project.test_forms.ContactForm',
            initial={'name': 'John'},
            access=GlueAccess.VIEW,
            unique_name='contact_form',
        )

        self.assertIsInstance(proxy, GlueFormProxy)
        self.assertEqual(proxy.target.__class__.__name__, 'ContactForm')

    def test_reconstructs_model_form_with_initial_data(self):
        """Should reconstruct ModelForm with initial data."""
        proxy = GlueFormProxy.from_action_request_data(
            form_class_path='test_project.test_forms.TestModelForm',
            initial={'name': 'Test Gorilla'},
            access=GlueAccess.CHANGE,
            unique_name='gorilla_form',
        )

        self.assertIsInstance(proxy, GlueFormProxy)
        # The form should be recreated with initial data
        self.assertEqual(proxy._get_initial_values()['name'], 'Test Gorilla')

    def test_reconstructs_model_form_without_instance(self):
        """Should reconstruct ModelForm without instance when pk is None."""
        proxy = GlueFormProxy.from_action_request_data(
            form_class_path='test_project.test_forms.TestModelForm',
            initial={},
            instance_pk=None,
            access=GlueAccess.CHANGE,
            unique_name='gorilla_form',
        )

        self.assertIsInstance(proxy, GlueFormProxy)
        self.assertIsNone(proxy.target.instance.pk)
