"""
Tests for GlueFormProxy get() action.
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_project.settings')
django.setup()

from django.test import TestCase

from django_glue.access.access import GlueAccess
from django_glue.proxies.form.proxy import GlueFormProxy
from django_glue.resolver.action import schemas as dto
from test_project.test_forms import ContactForm


class GlueFormProxyGetTestCase(TestCase):
    """Tests for GlueFormProxy.get() action."""

    def test_get_returns_fields(self):
        """get() should return field definitions."""
        form = ContactForm()
        proxy = GlueFormProxy(target=form, unique_name='contact_form', access=GlueAccess.VIEW)
        action_data = dto.ActionPayloadSchema(context_data={})
        result = proxy.get(action_data)

        self.assertIn('fields', result)
        self.assertIn('name', result['fields'])
        self.assertIn('email', result['fields'])

    def test_get_returns_values(self):
        """get() should return current values."""
        form = ContactForm(initial={'name': 'John'})
        proxy = GlueFormProxy(target=form, unique_name='contact_form', access=GlueAccess.VIEW)
        action_data = dto.ActionPayloadSchema(context_data={})
        result = proxy.get(action_data)

        self.assertIn('values', result)
        self.assertEqual(result['values']['name'], 'John')

    def test_get_returns_empty_errors(self):
        """get() should return empty errors dict."""
        form = ContactForm()
        proxy = GlueFormProxy(target=form, unique_name='contact_form', access=GlueAccess.VIEW)
        action_data = dto.ActionPayloadSchema(context_data={})
        result = proxy.get(action_data)

        self.assertIn('errors', result)
        self.assertEqual(result['errors'], {})

    def test_get_works_with_view_access(self):
        """get() should work with VIEW access."""
        form = ContactForm()
        proxy = GlueFormProxy(target=form, unique_name='contact_form', access=GlueAccess.VIEW)
        action_data = dto.ActionPayloadSchema(context_data={})
        result = proxy.get(action_data)

        self.assertIsNotNone(result)
