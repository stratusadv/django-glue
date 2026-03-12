"""
Tests for Django Glue all() action on QuerySetProxy.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_project.base_settings')
django.setup()

from django.test import TestCase

from django_glue.access.access import GlueAccess
from django_glue.proxies.queryset import GlueQuerySetProxy
from django_glue import data_transfer_objects as dto
from test_project.task.models import Task


class GlueQuerySetProxyAllTestCase(TestCase):
    """Tests for GlueQuerySetProxy.all() action."""

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
        self.task3 = Task.objects.create(
            title='Task 3',
            description='Third task',
            done=False,
            order=3
        )

    def test_all_returns_list_of_dicts(self):
        """all() action should return a list of model dictionaries."""
        proxy = GlueQuerySetProxy(
            target=Task.objects.all(),
            unique_name='tasks',
            access=GlueAccess.VIEW,
        )

        result = proxy.all()

        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 3)
        for item in result:
            self.assertIsInstance(item, dict)

    def test_all_includes_all_records(self):
        """all() action should return all records in the queryset."""
        proxy = GlueQuerySetProxy(
            target=Task.objects.all(),
            unique_name='tasks',
            access=GlueAccess.VIEW,
        )

        result = proxy.all()

        titles = [r['title'] for r in result]
        self.assertIn('Task 1', titles)
        self.assertIn('Task 2', titles)
        self.assertIn('Task 3', titles)

    def test_all_respects_queryset_filter(self):
        """all() action should respect filters on the underlying queryset."""
        proxy = GlueQuerySetProxy(
            target=Task.objects.filter(done=False),
            unique_name='tasks',
            access=GlueAccess.VIEW,
        )

        result = proxy.all()

        self.assertEqual(len(result), 2)
        for item in result:
            self.assertEqual(item['done'], False)

    def test_all_respects_fields_filter(self):
        """all() action should only include specified fields."""
        proxy = GlueQuerySetProxy(
            target=Task.objects.all(),
            unique_name='tasks',
            access=GlueAccess.VIEW,
            fields=['title', 'done'],
        )

        result = proxy.all()

        for item in result:
            self.assertIn('title', item)
            self.assertIn('done', item)
            self.assertNotIn('description', item)
            self.assertNotIn('order', item)

    def test_all_respects_exclude_filter(self):
        """all() action should exclude specified fields."""
        proxy = GlueQuerySetProxy(
            target=Task.objects.all(),
            unique_name='tasks',
            access=GlueAccess.VIEW,
            exclude=['description', 'order'],
        )

        result = proxy.all()

        for item in result:
            self.assertIn('title', item)
            self.assertIn('done', item)
            self.assertNotIn('description', item)
            self.assertNotIn('order', item)

    def test_all_works_with_view_access(self):
        """all() action should work with VIEW access level."""
        proxy = GlueQuerySetProxy(
            target=Task.objects.all(),
            unique_name='tasks',
            access=GlueAccess.VIEW,
        )

        action_data = dto.GlueActionRequestData(
            unique_name='tasks',
            action='all',
            post_data=None
        )

        # Should not raise
        result = proxy.process_action(action_data)
        self.assertEqual(len(result), 3)

    def test_all_works_with_higher_access_levels(self):
        """all() action should work with CHANGE and DELETE access levels."""
        for access in [GlueAccess.CHANGE, GlueAccess.DELETE]:
            proxy = GlueQuerySetProxy(
                target=Task.objects.all(),
                unique_name='tasks',
                access=access,
            )

            result = proxy.all()
            self.assertEqual(len(result), 3)

    def test_all_returns_empty_list_for_empty_queryset(self):
        """all() action should return empty list when queryset is empty."""
        Task.objects.all().delete()

        proxy = GlueQuerySetProxy(
            target=Task.objects.all(),
            unique_name='tasks',
            access=GlueAccess.VIEW,
        )

        result = proxy.all()

        self.assertEqual(result, [])