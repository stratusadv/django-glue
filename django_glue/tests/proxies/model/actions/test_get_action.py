"""
Tests for Django Glue get() action on ModelProxy.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_project.base_settings')
django.setup()

from django.test import TestCase

from django_glue.access.access import GlueAccess
from django_glue.proxies.model import GlueModelProxy
from django_glue import data_transfer_objects as dto
from test_project.task.models import Task


class GlueModelProxyGetTestCase(TestCase):
    """Tests for GlueModelProxy.get() action."""

    def setUp(self):
        """Create a test task for each test."""
        self.task = Task.objects.create(
            title='Test Task',
            description='A task for testing',
            done=False,
            order=42
        )

    def test_get_returns_model_as_dict(self):
        """get() action should return the model instance as a dictionary."""
        proxy = GlueModelProxy(
            target=self.task,
            unique_name='task',
            access=GlueAccess.VIEW,
        )

        result = proxy.get()

        self.assertIsInstance(result, dict)
        self.assertEqual(result['title'], 'Test Task')
        self.assertEqual(result['description'], 'A task for testing')
        self.assertEqual(result['done'], False)
        self.assertEqual(result['order'], 42)

    def test_get_includes_id_field(self):
        """get() action should include the id field."""
        proxy = GlueModelProxy(
            target=self.task,
            unique_name='task',
            access=GlueAccess.VIEW,
        )

        result = proxy.get()

        self.assertIn('id', result)
        self.assertEqual(result['id'], self.task.pk)

    def test_get_respects_fields_filter(self):
        """get() action should only include specified fields when fields parameter is used."""
        proxy = GlueModelProxy(
            target=self.task,
            unique_name='task',
            access=GlueAccess.VIEW,
            fields=['title', 'done'],
        )

        result = proxy.get()

        self.assertIn('title', result)
        self.assertIn('done', result)
        self.assertNotIn('description', result)
        self.assertNotIn('order', result)

    def test_get_respects_exclude_filter(self):
        """get() action should exclude specified fields when exclude parameter is used."""
        proxy = GlueModelProxy(
            target=self.task,
            unique_name='task',
            access=GlueAccess.VIEW,
            exclude=['description', 'order'],
        )

        result = proxy.get()

        self.assertIn('title', result)
        self.assertIn('done', result)
        self.assertNotIn('description', result)
        self.assertNotIn('order', result)

    def test_get_works_with_view_access(self):
        """get() action should work with VIEW access level."""
        proxy = GlueModelProxy(
            target=self.task,
            unique_name='task',
            access=GlueAccess.VIEW,
        )

        action_data = dto.GlueActionRequestData(
            unique_name='task',
            action='get',
            payload=None
        )

        # Should not raise
        result = proxy.process_action(action_data)
        self.assertIsNotNone(result)

    def test_get_works_with_higher_access_levels(self):
        """get() action should work with CHANGE and DELETE access levels."""
        for access in [GlueAccess.CHANGE, GlueAccess.DELETE]:
            proxy = GlueModelProxy(
                target=self.task,
                unique_name='task',
                access=access,
            )

            result = proxy.get()
            self.assertEqual(result['title'], 'Test Task')