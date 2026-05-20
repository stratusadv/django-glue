"""
Tests for GlueFormProxy validate() action.
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_project.settings')
django.setup()

from django.test import TestCase

from django_glue.access.access import GlueAccess
from django_glue.proxies.form.proxy import GlueFormProxy
from django_glue.exceptions import GlueAccessError
from django_glue.schemas import action_payload_schema as dto
from test_project.test_forms import ContactForm


class GlueFormProxyValidateTestCase(TestCase):
    """Tests for GlueFormProxy.validate() action."""

    def test_validate_returns_is_valid_true_for_valid_data(self):
        """validate() should return is_valid=True for valid data."""
        form = ContactForm()
        proxy = GlueFormProxy(target=form, unique_name='contact_form', access=GlueAccess.CHANGE)
        action_data = dto.ActionPayloadSchema(
            context_data={},
            post_data={
                'name': 'John Doe',
                'email': 'john@example.com',
                'message': 'Hello world',
                'priority': 'medium',
            },
        )
        result = proxy.validate(action_data)

        self.assertTrue(result['success'])
        self.assertIsNone(result['errors'])

    def test_validate_returns_is_valid_false_for_invalid_data(self):
        """validate() should return is_valid=False for invalid data."""
        form = ContactForm()
        proxy = GlueFormProxy(target=form, unique_name='contact_form', access=GlueAccess.CHANGE)
        action_data = dto.ActionPayloadSchema(
            context_data={},
            post_data={
                'name': '',  # Required field empty
                'email': 'not-an-email',  # Invalid email
                'message': 'Hello',
                'priority': 'medium',
            },
        )
        result = proxy.validate(action_data)

        self.assertFalse(result['success'])
        self.assertIn('name', result['errors'])
        self.assertIn('email', result['errors'])

    def test_validate_returns_cleaned_data_for_valid_form(self):
        """validate() should return cleaned_data when valid."""
        form = ContactForm()
        proxy = GlueFormProxy(target=form, unique_name='contact_form', access=GlueAccess.CHANGE)
        action_data = dto.ActionPayloadSchema(
            context_data={},
            post_data={
                'name': 'John Doe',
                'email': 'john@example.com',
                'message': 'Hello world',
                'priority': 'high',
            },
        )
        result = proxy.validate(action_data)

        self.assertIn('cleaned_data', result)
        self.assertEqual(result['cleaned_data']['name'], 'John Doe')
        self.assertEqual(result['cleaned_data']['priority'], 'high')

    def test_validate_returns_empty_cleaned_data_for_invalid_form(self):
        """validate() should return empty cleaned_data when invalid."""
        form = ContactForm()
        proxy = GlueFormProxy(target=form, unique_name='contact_form', access=GlueAccess.CHANGE)
        action_data = dto.ActionPayloadSchema(
            context_data={},
            post_data={'name': '', 'email': 'invalid', 'message': '', 'priority': 'medium'},
        )
        result = proxy.validate(action_data)

        self.assertEqual(result['cleaned_data'], {})

    def test_validate_requires_change_access(self):
        """validate() should require CHANGE access."""
        form = ContactForm()
        proxy = GlueFormProxy(target=form, unique_name='contact_form', access=GlueAccess.VIEW)

        action_data = dto.ActionPayloadSchema(context_data={}, post_data={'name': 'Test'})

        with self.assertRaises(GlueAccessError):
            proxy.process_action('validate', action_data)

    def test_validate_errors_are_lists(self):
        """validate() should return errors as lists of strings."""
        form = ContactForm()
        proxy = GlueFormProxy(target=form, unique_name='contact_form', access=GlueAccess.CHANGE)
        action_data = dto.ActionPayloadSchema(
            context_data={},
            post_data={
                'name': '',
                'email': 'john@example.com',
                'message': 'Hello',
                'priority': 'medium',
            },
        )
        result = proxy.validate(action_data)

        self.assertIsInstance(result['errors']['name'], list)
        self.assertTrue(len(result['errors']['name']) > 0)
