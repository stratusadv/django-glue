"""
Tests for Django Glue delete() action on ModelProxy.
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


class GlueModelProxyDeleteTestCase(TestCase):
    """Tests for GlueModelProxy.delete() action."""

    def setUp(self):
        """Create a test task for each test."""
        self.task = Task.objects.create(
            title='Test Task',
            description='A task to delete',
            done=False,
            order=1
        )

    def test_delete_removes_instance_from_database(self):
        """delete() action should remove the model instance from the database."""
        task_pk = self.task.pk

        proxy = GlueModelProxy(
            target=self.task,
            unique_name='task',
            access=GlueAccess.DELETE,
        )

        # Call delete action
        proxy.delete()

        # Verify instance is deleted
        self.assertFalse(Task.objects.filter(pk=task_pk).exists())

    def test_delete_requires_delete_access(self):
        """delete() action should require DELETE access level."""
        proxy = GlueModelProxy(
            target=self.task,
            unique_name='task',
            access=GlueAccess.VIEW,  # Insufficient access
        )

        action_data = dto.GlueActionRequestData(
            unique_name='task',
            action='delete',
            payload=None
        )

        with self.assertRaises(GlueAccessError):
            proxy.process_action(action_data)

    def test_delete_with_change_access_raises_error(self):
        """delete() action should fail with only CHANGE access."""
        proxy = GlueModelProxy(
            target=self.task,
            unique_name='task',
            access=GlueAccess.CHANGE,  # Not enough for delete
        )

        action_data = dto.GlueActionRequestData(
            unique_name='task',
            action='delete',
            payload=None
        )

        with self.assertRaises(GlueAccessError):
            proxy.process_action(action_data)
