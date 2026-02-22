"""
Tests for Django Glue filter() action on QuerySetProxy.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_project.base_settings')
django.setup()

from django.test import TestCase

from django_glue.access.access import GlueAccess
from django_glue.proxies.queryset.proxy import GlueQuerySetProxy
from django_glue.exceptions import GlueQuerySetFilterValidationError
from django_glue import data_transfer_objects as dto
from test_project.task.models import Task


class GlueQuerySetProxyFilterTestCase(TestCase):
    """Tests for GlueQuerySetProxy.filter() action."""

    def setUp(self):
        """Create test tasks for each test."""
        self.task1 = Task.objects.create(
            title='Important Task',
            description='This is urgent work',
            done=False,
            order=1
        )
        self.task2 = Task.objects.create(
            title='Regular Task',
            description='Normal priority',
            done=True,
            order=2
        )
        self.task3 = Task.objects.create(
            title='Another Important Item',
            description='Also urgent',
            done=False,
            order=3
        )

    def test_filter_applies_exact_match(self):
        """filter() action should apply exact match filter."""
        proxy = GlueQuerySetProxy(
            target=Task.objects.all(),
            unique_name='tasks',
            access=GlueAccess.VIEW,
        )

        result = proxy.filter({'done': True})

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['title'], 'Regular Task')

    def test_filter_applies_icontains_lookup(self):
        """filter() action should support __icontains lookup."""
        proxy = GlueQuerySetProxy(
            target=Task.objects.all(),
            unique_name='tasks',
            access=GlueAccess.VIEW,
        )

        result = proxy.filter({'title__icontains': 'important'})

        self.assertEqual(len(result), 2)
        titles = [r['title'] for r in result]
        self.assertIn('Important Task', titles)
        self.assertIn('Another Important Item', titles)

    def test_filter_applies_multiple_criteria(self):
        """filter() action should support multiple filter criteria."""
        proxy = GlueQuerySetProxy(
            target=Task.objects.all(),
            unique_name='tasks',
            access=GlueAccess.VIEW,
        )

        result = proxy.filter({
            'done': False,
            'title__icontains': 'important',
        })

        self.assertEqual(len(result), 2)

    def test_filter_validates_field_against_included_fields(self):
        """filter() action should raise error for fields not in _included_fields."""
        proxy = GlueQuerySetProxy(
            target=Task.objects.all(),
            unique_name='tasks',
            access=GlueAccess.VIEW,
            fields=['title', 'done'],  # description and order excluded
        )

        with self.assertRaises(GlueQuerySetFilterValidationError) as context:
            proxy.filter({'description__icontains': 'urgent'})

        self.assertEqual(context.exception.field, 'description')

    def test_filter_validates_base_field_from_lookup(self):
        """filter() action should validate base field name from ORM lookups."""
        proxy = GlueQuerySetProxy(
            target=Task.objects.all(),
            unique_name='tasks',
            access=GlueAccess.VIEW,
            fields=['title', 'done'],
        )

        # order__gte should fail because 'order' is not in fields
        with self.assertRaises(GlueQuerySetFilterValidationError) as context:
            proxy.filter({'order__gte': 2})

        self.assertEqual(context.exception.field, 'order')

    def test_filter_allows_valid_fields(self):
        """filter() action should allow filtering on included fields."""
        proxy = GlueQuerySetProxy(
            target=Task.objects.all(),
            unique_name='tasks',
            access=GlueAccess.VIEW,
            fields=['title', 'done'],
        )

        # Should not raise - title is in fields
        result = proxy.filter({'title__icontains': 'task'})
        self.assertGreater(len(result), 0)

    def test_filter_returns_list_of_dicts(self):
        """filter() action should return a list of model dictionaries."""
        proxy = GlueQuerySetProxy(
            target=Task.objects.all(),
            unique_name='tasks',
            access=GlueAccess.VIEW,
        )

        result = proxy.filter({'done': False})

        self.assertIsInstance(result, list)
        for item in result:
            self.assertIsInstance(item, dict)

    def test_filter_respects_fields_in_output(self):
        """filter() action should only include specified fields in output."""
        proxy = GlueQuerySetProxy(
            target=Task.objects.all(),
            unique_name='tasks',
            access=GlueAccess.VIEW,
            fields=['title', 'done'],
        )

        result = proxy.filter({'done': False})

        for item in result:
            self.assertIn('title', item)
            self.assertIn('done', item)
            self.assertNotIn('description', item)
            self.assertNotIn('order', item)

    def test_filter_works_with_view_access(self):
        """filter() action should work with VIEW access level."""
        proxy = GlueQuerySetProxy(
            target=Task.objects.all(),
            unique_name='tasks',
            access=GlueAccess.VIEW,
        )

        action_data = dto.GlueActionRequestData(
            unique_name='tasks',
            action='filter',
            payload={'done': True}
        )

        # Should not raise
        result = proxy.process_action(action_data)
        self.assertIsNotNone(result)

    def test_filter_returns_empty_list_for_no_matches(self):
        """filter() action should return empty list when no records match."""
        proxy = GlueQuerySetProxy(
            target=Task.objects.all(),
            unique_name='tasks',
            access=GlueAccess.VIEW,
        )

        result = proxy.filter({'title': 'Nonexistent Task'})

        self.assertEqual(result, [])

    def test_filter_error_includes_allowed_fields(self):
        """GlueQuerySetFilterValidationError should include list of allowed fields."""
        proxy = GlueQuerySetProxy(
            target=Task.objects.all(),
            unique_name='tasks',
            access=GlueAccess.VIEW,
            fields=['title', 'done'],
        )

        with self.assertRaises(GlueQuerySetFilterValidationError) as context:
            proxy.filter({'order': 1})

        self.assertIn('title', context.exception.allowed_fields)
        self.assertIn('done', context.exception.allowed_fields)