"""
Tests for Django Glue delete() action on ModelProxy.
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_project.settings')
django.setup()

from django.test import TestCase

from django_glue.access.access import GlueAccess
from django_glue.proxies import GlueModelInstanceProxy
from django_glue.exceptions import GlueAccessError
from django_glue.resolver.action import schemas as dto
from test_project.gorilla.models import Gorilla


class GlueModelProxyDeleteTestCase(TestCase):
    """Tests for GlueModelProxy.delete() action."""

    def setUp(self):
        """Create a test gorilla for each test."""
        self.gorilla = Gorilla.objects.create(
            name='Test Gorilla', description='A gorilla to delete', age=25, weight=350.0, height=1.8
        )

    def test_delete_removes_instance_from_database(self):
        """delete() action should remove the model instance from the database."""
        gorilla_pk = self.gorilla.pk

        proxy = GlueModelInstanceProxy(target=self.gorilla, unique_name='gorilla', access=GlueAccess.DELETE)

        # Call delete action
        action_data = dto.ActionRequest(proxy_definition={})
        proxy.delete(action_data)

        # Verify instance is deleted
        self.assertFalse(Gorilla.objects.filter(pk=gorilla_pk).exists())

    def test_delete_requires_delete_access(self):
        """delete() action should require DELETE access level."""
        proxy = GlueModelInstanceProxy(
            target=self.gorilla,
            unique_name='gorilla',
            access=GlueAccess.VIEW,  # Insufficient access
        )

        action_data = dto.ActionRequest(proxy_definition={})

        with self.assertRaises(GlueAccessError):
            proxy.process_action('delete', action_data)

    def test_delete_with_change_access_raises_error(self):
        """delete() action should fail with only CHANGE access."""
        proxy = GlueModelInstanceProxy(
            target=self.gorilla,
            unique_name='gorilla',
            access=GlueAccess.CHANGE,  # Not enough for delete
        )

        action_data = dto.ActionRequest(proxy_definition={})

        with self.assertRaises(GlueAccessError):
            proxy.process_action('delete', action_data)
