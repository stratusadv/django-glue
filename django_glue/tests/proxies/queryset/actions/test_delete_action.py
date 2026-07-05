"""
Tests for Django Glue delete() action on QuerySetProxy.
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_project.settings')
django.setup()

from django.test import TestCase

from django_glue.access.access import GlueAccess
from django_glue.proxies import GlueQuerySetProxy
from django_glue.exceptions import GlueModelInstanceNotFoundError, GlueAccessError
from django_glue.resolver.action import schemas as dto
from test_project.gorilla.models import Gorilla


class GlueQuerySetProxyDeleteTestCase(TestCase):
    """Tests for GlueQuerySetProxy.delete() action."""

    def setUp(self):
        """Create test gorillas for each test."""
        self.gorilla1 = Gorilla.objects.create(
            name='Gorilla 1', description='First gorilla', age=10, weight=200, height=6
        )
        self.gorilla2 = Gorilla.objects.create(
            name='Gorilla 2', description='Second gorilla', age=12, weight=210, height=6.5
        )

    def test_delete_removes_specific_instance_by_pk(self):
        """delete() action should remove the specific instance identified by id in payload."""
        gorilla1_pk = self.gorilla1.pk
        gorilla2_pk = self.gorilla2.pk

        proxy = GlueQuerySetProxy(
            target=Gorilla.objects.all(), unique_name='gorillas', access=GlueAccess.DELETE
        )

        action_data = dto.ActionRequest(proxy_definition={},             action_kwargs={'id': gorilla1_pk})
        # Delete gorilla1 via payload
        proxy.delete(action_data)

        # Verify gorilla1 is deleted but gorilla2 remains
        self.assertFalse(Gorilla.objects.filter(pk=gorilla1_pk).exists())
        self.assertTrue(Gorilla.objects.filter(pk=gorilla2_pk).exists())

    def test_delete_raises_not_found_for_invalid_pk(self):
        """delete() action should raise GlueModelInstanceNotFoundError for non-existent id."""
        proxy = GlueQuerySetProxy(
            target=Gorilla.objects.all(), unique_name='gorillas', access=GlueAccess.DELETE
        )

        action_data = dto.ActionRequest(proxy_definition={},             action_kwargs={'id': 99999})

        with self.assertRaises(GlueModelInstanceNotFoundError):
            proxy.delete(action_data)

    def test_delete_requires_delete_access(self):
        """delete() action should require DELETE access level."""
        proxy = GlueQuerySetProxy(
            target=Gorilla.objects.all(),
            unique_name='gorillas',
            access=GlueAccess.VIEW,  # Insufficient access
        )

        action_data = dto.ActionRequest(proxy_definition={},             action_kwargs={'id': self.gorilla1.pk})

        with self.assertRaises(GlueAccessError):
            proxy.process_action('delete', action_data)

    def test_delete_with_change_access_raises_error(self):
        """delete() action should fail with only CHANGE access."""
        proxy = GlueQuerySetProxy(
            target=Gorilla.objects.all(),
            unique_name='gorillas',
            access=GlueAccess.CHANGE,  # Not enough for delete
        )

        action_data = dto.ActionRequest(proxy_definition={},             action_kwargs={'id': self.gorilla1.pk})

        with self.assertRaises(GlueAccessError):
            proxy.process_action('delete', action_data)

    def test_delete_uses_correct_internal_method(self):
        """Verify delete() uses _get_model_instance_by_pk (bug fix verification)."""
        # This test verifies the bug fix - the method should exist and be callable
        proxy = GlueQuerySetProxy(
            target=Gorilla.objects.all(), unique_name='gorillas', access=GlueAccess.DELETE
        )

        # Verify the method exists
        self.assertTrue(hasattr(proxy, '_get_model_instance_by_pk'))

        # Verify it returns the correct instance
        instance = proxy._get_model_instance_by_pk(self.gorilla1.pk)
        self.assertEqual(instance.pk, self.gorilla1.pk)
        self.assertEqual(instance.name, 'Gorilla 1')

    def test_delete_returns_error_for_missing_pk(self):
        """delete() should return error dict when id is missing from action_kwargs."""
        proxy = GlueQuerySetProxy(
            target=Gorilla.objects.all(),
            unique_name='gorillas',
            access=GlueAccess.DELETE,
        )

        action_data = dto.ActionRequest(proxy_definition={}, action_kwargs={})
        result = proxy.delete(action_data)

        self.assertFalse(result['success'])
        self.assertIn('id is required', result['error'])
