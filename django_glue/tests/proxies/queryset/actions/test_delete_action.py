"""
Tests for Django Glue delete() action on QuerySetProxy.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_project.base_settings')
django.setup()

from django.test import TestCase

from django_glue.access.access import GlueAccess
from django_glue.proxies.queryset import GlueQuerySetProxy
from django_glue.exceptions import GlueModelInstanceNotFoundError, GlueAccessError
from django_glue import data_transfer_objects as dto
from test_project.task.models import Task


class GlueQuerySetProxyDeleteTestCase(TestCase):
    """Tests for GlueQuerySetProxy.delete() action."""

    def setUp(self):
        """Create test tasks for each test."""
        self.task1 = Task.objects.create(
            title='Task 1',
            description='First task',
            done=False,
            order=1
        )
        self.task2 = Task.objects.create(
            title='Task 2',
            description='Second task',
            done=True,
            order=2
        )

    def test_delete_removes_specific_instance_by_pk(self):
        """delete() action should remove the specific instance identified by id in payload."""
        task1_pk = self.task1.pk
        task2_pk = self.task2.pk

        proxy = GlueQuerySetProxy(
            target=Task.objects.all(),
            unique_name='tasks',
            access=GlueAccess.DELETE,
        )

        # Delete task1 via payload
        proxy.delete({'id': task1_pk})

        # Verify task1 is deleted but task2 remains
        self.assertFalse(Task.objects.filter(pk=task1_pk).exists())
        self.assertTrue(Task.objects.filter(pk=task2_pk).exists())

    def test_delete_raises_not_found_for_invalid_pk(self):
        """delete() action should raise GlueModelInstanceNotFoundError for non-existent id."""
        proxy = GlueQuerySetProxy(
            target=Task.objects.all(),
            unique_name='tasks',
            access=GlueAccess.DELETE,
        )

        with self.assertRaises(GlueModelInstanceNotFoundError):
            proxy.delete({'id': 99999})

    def test_delete_requires_delete_access(self):
        """delete() action should require DELETE access level."""
        proxy = GlueQuerySetProxy(
            target=Task.objects.all(),
            unique_name='tasks',
            access=GlueAccess.VIEW,  # Insufficient access
        )

        action_data = dto.GlueActionRequestData(
            unique_name='tasks',
            action='delete',
            payload={'id': self.task1.pk}
        )

        with self.assertRaises(GlueAccessError):
            proxy.process_action(action_data)

    def test_delete_with_change_access_raises_error(self):
        """delete() action should fail with only CHANGE access."""
        proxy = GlueQuerySetProxy(
            target=Task.objects.all(),
            unique_name='tasks',
            access=GlueAccess.CHANGE,  # Not enough for delete
        )

        action_data = dto.GlueActionRequestData(
            unique_name='tasks',
            action='delete',
            payload={'id': self.task1.pk}
        )

        with self.assertRaises(GlueAccessError):
            proxy.process_action(action_data)

    def test_delete_uses_correct_internal_method(self):
        """Verify delete() uses _get_model_instance_by_pk (bug fix verification)."""
        # This test verifies the bug fix - the method should exist and be callable
        proxy = GlueQuerySetProxy(
            target=Task.objects.all(),
            unique_name='tasks',
            access=GlueAccess.DELETE,
        )

        # Verify the method exists
        self.assertTrue(hasattr(proxy, '_get_model_instance_by_pk'))

        # Verify it returns the correct instance
        instance = proxy._get_model_instance_by_pk(self.task1.pk)
        self.assertEqual(instance.pk, self.task1.pk)
        self.assertEqual(instance.title, 'Task 1')