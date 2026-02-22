"""
Tests for Django Glue save() action on ModelProxy.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_project.base_settings')
django.setup()

from django.test import TestCase

from django_glue.access.access import GlueAccess
from django_glue.proxies.model.proxy import GlueModelProxy
from django_glue.exceptions import GlueAccessError
from django_glue import data_transfer_objects as dto
from test_project.task.models import Task


class GlueModelProxySaveTestCase(TestCase):
    """Tests for GlueModelProxy.save() action."""

    def setUp(self):
        """Create a test task for each test."""
        self.task = Task.objects.create(
            title='Original Title',
            description='Original description',
            done=False,
            order=1
        )

    def test_save_updates_instance_fields(self):
        """save() action should update model instance fields from payload."""
        proxy = GlueModelProxy(
            target=self.task,
            unique_name='task',
            access=GlueAccess.CHANGE,
        )

        proxy.save({
            'title': 'Updated Title',
            'done': True,
        })

        # Refresh from database
        self.task.refresh_from_db()

        self.assertEqual(self.task.title, 'Updated Title')
        self.assertEqual(self.task.done, True)
        # Unchanged fields should remain
        self.assertEqual(self.task.description, 'Original description')
        self.assertEqual(self.task.order, 1)

    def test_save_persists_to_database(self):
        """save() action should persist changes to the database."""
        proxy = GlueModelProxy(
            target=self.task,
            unique_name='task',
            access=GlueAccess.CHANGE,
        )

        proxy.save({'title': 'Persisted Title'})

        # Fetch fresh from database
        fresh_task = Task.objects.get(pk=self.task.pk)
        self.assertEqual(fresh_task.title, 'Persisted Title')

    def test_save_returns_updated_dict(self):
        """save() action should return the updated model as a dictionary."""
        proxy = GlueModelProxy(
            target=self.task,
            unique_name='task',
            access=GlueAccess.CHANGE,
        )

        result = proxy.save({'title': 'New Title'})

        self.assertIsInstance(result, dict)
        self.assertEqual(result['title'], 'New Title')

    def test_save_only_updates_included_fields(self):
        """save() action should ignore payload keys not in _included_fields."""
        proxy = GlueModelProxy(
            target=self.task,
            unique_name='task',
            access=GlueAccess.CHANGE,
            fields=['title', 'done'],  # Only these fields are allowed
        )

        proxy.save({
            'title': 'Allowed Update',
            'description': 'Should be ignored',  # Not in fields
            'order': 999,  # Not in fields
        })

        self.task.refresh_from_db()

        self.assertEqual(self.task.title, 'Allowed Update')
        self.assertEqual(self.task.description, 'Original description')  # Unchanged
        self.assertEqual(self.task.order, 1)  # Unchanged

    def test_save_requires_change_access(self):
        """save() action should require at least CHANGE access level."""
        proxy = GlueModelProxy(
            target=self.task,
            unique_name='task',
            access=GlueAccess.VIEW,  # Insufficient access
        )

        action_data = dto.GlueActionRequestData(
            unique_name='task',
            action='save',
            payload={'title': 'Should Fail'}
        )

        with self.assertRaises(GlueAccessError):
            proxy.process_action(action_data)

    def test_save_works_with_delete_access(self):
        """save() action should work with DELETE access level (cascading)."""
        proxy = GlueModelProxy(
            target=self.task,
            unique_name='task',
            access=GlueAccess.DELETE,
        )

        result = proxy.save({'title': 'Updated with DELETE access'})

        self.assertEqual(result['title'], 'Updated with DELETE access')