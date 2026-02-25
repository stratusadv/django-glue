"""
Tests for Django Glue save() action on QuerySetProxy.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_project.base_settings')
django.setup()

from django.test import TestCase

from django_glue.access.access import GlueAccess
from django_glue.proxies.queryset.proxy import GlueQuerySetProxy
from django_glue.exceptions import GlueAccessError, GlueModelInstanceNotFoundError
from django_glue import data_transfer_objects as dto
from test_project.task.models import Task


class GlueQuerySetProxySaveTestCase(TestCase):
    """Tests for GlueQuerySetProxy.save() action."""

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

    def test_save_updates_specific_instance_by_pk(self):
        """save() action should update the specific instance identified by id in payload."""
        proxy = GlueQuerySetProxy(
            target=Task.objects.all(),
            unique_name='tasks',
            access=GlueAccess.CHANGE,
        )

        proxy.save({
            'id': self.task1.pk,
            'title': 'Updated Task 1',
        })

        self.task1.refresh_from_db()
        self.task2.refresh_from_db()

        self.assertEqual(self.task1.title, 'Updated Task 1')
        self.assertEqual(self.task2.title, 'Task 2')  # Unchanged

    def test_save_returns_updated_dict(self):
        """save() action should return the updated model as a dictionary."""
        proxy = GlueQuerySetProxy(
            target=Task.objects.all(),
            unique_name='tasks',
            access=GlueAccess.CHANGE,
        )

        result = proxy.save({
            'id': self.task1.pk,
            'title': 'New Title',
        })

        self.assertIsInstance(result, dict)
        self.assertEqual(result['title'], 'New Title')

    def test_save_raises_not_found_for_invalid_pk(self):
        """save() action should raise GlueModelInstanceNotFoundError for non-existent id."""
        proxy = GlueQuerySetProxy(
            target=Task.objects.all(),
            unique_name='tasks',
            access=GlueAccess.CHANGE,
        )

        with self.assertRaises(GlueModelInstanceNotFoundError):
            proxy.save({'id': 99999, 'title': 'Should Fail'})

    def test_save_requires_change_access(self):
        """save() action should require at least CHANGE access level."""
        proxy = GlueQuerySetProxy(
            target=Task.objects.all(),
            unique_name='tasks',
            access=GlueAccess.VIEW,  # Insufficient access
        )

        action_data = dto.GlueActionRequestData(
            unique_name='tasks',
            action='save',
            payload={'id': self.task1.pk, 'title': 'Should Fail'}
        )

        with self.assertRaises(GlueAccessError):
            proxy.process_action(action_data)

    def test_save_works_with_delete_access(self):
        """save() action should work with DELETE access level (cascading)."""
        proxy = GlueQuerySetProxy(
            target=Task.objects.all(),
            unique_name='tasks',
            access=GlueAccess.DELETE,
        )

        result = proxy.save({
            'id': self.task1.pk,
            'title': 'Updated with DELETE access',
        })

        self.assertEqual(result['title'], 'Updated with DELETE access')
