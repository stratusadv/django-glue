"""
Tests for Django Glue query_with_params() action on QuerySetProxy.

This tests both basic querying (previously all()) and filtering (previously filter()).
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_project.settings')
django.setup()

from django.test import TestCase

from django_glue.access.access import GlueAccess
from django_glue.proxies import GlueQuerySetProxy
from django_glue.resolver.action import schemas as dto
from test_project.gorilla.models import Gorilla


class GlueQuerySetProxyQueryWithParamsBasicTestCase(TestCase):
    """Tests for GlueQuerySetProxy.query_with_params() basic functionality."""

    def setUp(self):
        """Create test gorillas for each test."""
        self.gorilla1 = Gorilla.objects.create(
            name='Gorilla 1', description='First gorilla', age=18, weight=200.0, height=1.8
        )
        self.gorilla2 = Gorilla.objects.create(
            name='Gorilla 2', description='Second gorilla', age=25, weight=250.0, height=2.0
        )
        self.gorilla3 = Gorilla.objects.create(
            name='Gorilla 3', description='Third gorilla', age=30, weight=300.0, height=2.2
        )

    def test_query_with_params_returns_list_of_dicts(self):
        """query_with_params() action should return a list of model dictionaries."""
        proxy = GlueQuerySetProxy(
            target=Gorilla.objects.all(), unique_name='gorillas', access=GlueAccess.VIEW
        )

        action_data = dto.ActionPayloadSchema(context_data={})
        result = proxy.query_with_params(action_data)

        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 3)
        for item in result:
            self.assertIsInstance(item, dict)

    def test_query_with_params_includes_all_records(self):
        """query_with_params() action should return all records in the queryset."""
        proxy = GlueQuerySetProxy(
            target=Gorilla.objects.all(), unique_name='gorillas', access=GlueAccess.VIEW
        )

        action_data = dto.ActionPayloadSchema(context_data={})
        result = proxy.query_with_params(action_data)

        names = [r['name'] for r in result]
        self.assertIn('Gorilla 1', names)
        self.assertIn('Gorilla 2', names)
        self.assertIn('Gorilla 3', names)

    def test_query_with_params_respects_queryset_filter(self):
        """query_with_params() action should respect filters on the underlying queryset."""
        proxy = GlueQuerySetProxy(
            target=Gorilla.objects.filter(age__gte=25),
            unique_name='gorillas',
            access=GlueAccess.VIEW,
        )

        action_data = dto.ActionPayloadSchema(context_data={})
        result = proxy.query_with_params(action_data)

        self.assertEqual(len(result), 2)
        for item in result:
            self.assertGreaterEqual(item['age'], 25)

    def test_query_with_params_respects_fields_filter(self):
        """query_with_params() action should only include specified fields."""
        proxy = GlueQuerySetProxy(
            target=Gorilla.objects.all(),
            unique_name='gorillas',
            access=GlueAccess.VIEW,
            fields=['name', 'age'],
        )

        action_data = dto.ActionPayloadSchema(context_data={})
        result = proxy.query_with_params(action_data)

        for item in result:
            self.assertIn('name', item)
            self.assertIn('age', item)
            self.assertNotIn('description', item)
            self.assertNotIn('weight', item)

    def test_query_with_params_respects_exclude_filter(self):
        """query_with_params() action should exclude specified fields."""
        proxy = GlueQuerySetProxy(
            target=Gorilla.objects.all(),
            unique_name='gorillas',
            access=GlueAccess.VIEW,
            exclude=['description', 'weight'],
        )

        action_data = dto.ActionPayloadSchema(context_data={})
        result = proxy.query_with_params(action_data)

        for item in result:
            self.assertIn('name', item)
            self.assertIn('age', item)
            self.assertNotIn('description', item)
            self.assertNotIn('weight', item)

    def test_query_with_params_works_with_view_access(self):
        """query_with_params() action should work with VIEW access level."""
        proxy = GlueQuerySetProxy(
            target=Gorilla.objects.all(), unique_name='gorillas', access=GlueAccess.VIEW
        )

        action_data = dto.ActionPayloadSchema(context_data={})

        # Should not raise
        result = proxy.process_action('query_with_params', action_data)
        self.assertEqual(len(result), 3)

    def test_query_with_params_works_with_higher_access_levels(self):
        """query_with_params() action should work with CHANGE and DELETE access levels."""
        for access in [GlueAccess.CHANGE, GlueAccess.DELETE]:
            proxy = GlueQuerySetProxy(
                target=Gorilla.objects.all(), unique_name='gorillas', access=access
            )

            action_data = dto.ActionPayloadSchema(context_data={})
            result = proxy.query_with_params(action_data)
            self.assertEqual(len(result), 3)

    def test_query_with_params_returns_empty_list_for_empty_queryset(self):
        """query_with_params() action should return empty list when queryset is empty."""
        Gorilla.objects.all().delete()

        proxy = GlueQuerySetProxy(
            target=Gorilla.objects.all(), unique_name='gorillas', access=GlueAccess.VIEW
        )

        action_data = dto.ActionPayloadSchema(context_data={})
        result = proxy.query_with_params(action_data)

        self.assertEqual(result, [])


class GlueQuerySetProxyQueryWithParamsFilterTestCase(TestCase):
    """Tests for GlueQuerySetProxy.query_with_params() with filter params."""

    def setUp(self):
        """Create test gorillas for each test."""
        self.gorilla1 = Gorilla.objects.create(
            name='Important Gorilla',
            description='This is urgent work',
            age=30,
            weight=200.0,
            height=1.8,
        )
        self.gorilla2 = Gorilla.objects.create(
            name='Regular Gorilla', description='Normal priority', age=25, weight=250.0, height=2.0
        )
        self.gorilla3 = Gorilla.objects.create(
            name='Another Important Item',
            description='Also urgent',
            age=35,
            weight=300.0,
            height=2.2,
        )

    def test_filter_applies_exact_match(self):
        """query_with_params() action should apply exact match filter."""
        proxy = GlueQuerySetProxy(
            target=Gorilla.objects.all(), unique_name='gorillas', access=GlueAccess.VIEW
        )

        action_data = dto.ActionPayloadSchema(context_data={}, user_data={'filter': {'age': 25}})
        result = proxy.query_with_params(action_data)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['name'], 'Regular Gorilla')

    def test_filter_applies_icontains_lookup(self):
        """query_with_params() action should support __icontains lookup."""
        proxy = GlueQuerySetProxy(
            target=Gorilla.objects.all(), unique_name='gorillas', access=GlueAccess.VIEW
        )

        action_data = dto.ActionPayloadSchema(
            context_data={}, user_data={'filter': {'name__icontains': 'important'}}
        )
        result = proxy.query_with_params(action_data)

        self.assertEqual(len(result), 2)
        names = [r['name'] for r in result]
        self.assertIn('Important Gorilla', names)
        self.assertIn('Another Important Item', names)

    def test_filter_applies_multiple_criteria(self):
        """query_with_params() action should support multiple filter criteria."""
        proxy = GlueQuerySetProxy(
            target=Gorilla.objects.all(), unique_name='gorillas', access=GlueAccess.VIEW
        )

        action_data = dto.ActionPayloadSchema(
            context_data={}, user_data={'filter': {'age__gte': 25, 'name__icontains': 'important'}}
        )
        result = proxy.query_with_params(action_data)

        self.assertEqual(len(result), 2)

    def test_filter_returns_list_of_dicts(self):
        """query_with_params() action should return a list of model dictionaries."""
        proxy = GlueQuerySetProxy(
            target=Gorilla.objects.all(), unique_name='gorillas', access=GlueAccess.VIEW
        )

        action_data = dto.ActionPayloadSchema(
            context_data={}, user_data={'filter': {'age__gte': 25}}
        )
        result = proxy.query_with_params(action_data)

        self.assertIsInstance(result, list)
        for item in result:
            self.assertIsInstance(item, dict)

    def test_filter_respects_fields_in_output(self):
        """query_with_params() action should only include specified fields in output."""
        proxy = GlueQuerySetProxy(
            target=Gorilla.objects.all(),
            unique_name='gorillas',
            access=GlueAccess.VIEW,
            fields=['name', 'age'],
        )

        action_data = dto.ActionPayloadSchema(
            context_data={}, user_data={'filter': {'age__gte': 25}}
        )
        result = proxy.query_with_params(action_data)

        for item in result:
            self.assertIn('name', item)
            self.assertIn('age', item)
            self.assertNotIn('description', item)
            self.assertNotIn('weight', item)

    def test_filter_works_with_view_access(self):
        """query_with_params() with filter should work with VIEW access level."""
        proxy = GlueQuerySetProxy(
            target=Gorilla.objects.all(), unique_name='gorillas', access=GlueAccess.VIEW
        )

        action_data = dto.ActionPayloadSchema(context_data={}, user_data={'filter': {'age': 25}})

        # Should not raise
        result = proxy.process_action('query_with_params', action_data)
        self.assertIsNotNone(result)

    def test_filter_returns_empty_list_for_no_matches(self):
        """query_with_params() with filter should return empty list when no records match."""
        proxy = GlueQuerySetProxy(
            target=Gorilla.objects.all(), unique_name='gorillas', access=GlueAccess.VIEW
        )

        action_data = dto.ActionPayloadSchema(
            context_data={}, user_data={'filter': {'name': 'Nonexistent Gorilla'}}
        )
        result = proxy.query_with_params(action_data)

        self.assertEqual(result, [])


class GlueQuerySetProxyQueryWithParamsOrderByTestCase(TestCase):
    """Tests for GlueQuerySetProxy.query_with_params() with order_by params."""

    def setUp(self):
        """Create test gorillas for each test."""
        self.gorilla1 = Gorilla.objects.create(
            name='Gorilla A', description='First gorilla', age=30, weight=300.0, height=2.2
        )
        self.gorilla2 = Gorilla.objects.create(
            name='Gorilla B', description='Second gorilla', age=18, weight=200.0, height=1.8
        )
        self.gorilla3 = Gorilla.objects.create(
            name='Gorilla C', description='Third gorilla', age=25, weight=250.0, height=2.0
        )

    def test_order_by_ascending(self):
        """query_with_params() should support ascending order_by."""
        proxy = GlueQuerySetProxy(
            target=Gorilla.objects.all(), unique_name='gorillas', access=GlueAccess.VIEW
        )

        action_data = dto.ActionPayloadSchema(context_data={}, user_data={'order_by': 'age'})
        result = proxy.query_with_params(action_data)

        self.assertEqual(result[0]['age'], 18)
        self.assertEqual(result[1]['age'], 25)
        self.assertEqual(result[2]['age'], 30)

    def test_order_by_descending(self):
        """query_with_params() should support descending order_by."""
        proxy = GlueQuerySetProxy(
            target=Gorilla.objects.all(), unique_name='gorillas', access=GlueAccess.VIEW
        )

        action_data = dto.ActionPayloadSchema(context_data={}, user_data={'order_by': '-age'})
        result = proxy.query_with_params(action_data)

        self.assertEqual(result[0]['age'], 30)
        self.assertEqual(result[1]['age'], 25)
        self.assertEqual(result[2]['age'], 18)

    def test_order_by_list(self):
        """query_with_params() should support order_by as a list."""
        proxy = GlueQuerySetProxy(
            target=Gorilla.objects.all(), unique_name='gorillas', access=GlueAccess.VIEW
        )

        action_data = dto.ActionPayloadSchema(
            context_data={}, user_data={'order_by': ['age', 'weight']}
        )
        result = proxy.query_with_params(action_data)

        # sorted by age ascending, then weight
        self.assertEqual(result[0]['age'], 18)
        self.assertEqual(result[0]['weight'], 200.0)


class GlueQuerySetProxyQueryWithParamsSliceTestCase(TestCase):
    """Tests for GlueQuerySetProxy.query_with_params() with slice params."""

    def setUp(self):
        """Create test gorillas for each test."""
        for i in range(10):
            Gorilla.objects.create(
                name=f'Gorilla {i}',
                description=f'Gorilla number {i}',
                age=i,
                weight=200.0 + (i * 10.0),
                height=1.8 + (i * 0.1),
            )

    def test_slice_with_start_and_stop(self):
        """query_with_params() should support slicing with start and stop."""
        proxy = GlueQuerySetProxy(
            target=Gorilla.objects.all().order_by('age'),
            unique_name='gorillas',
            access=GlueAccess.VIEW,
        )

        action_data = dto.ActionPayloadSchema(
            context_data={}, user_data={'slice': {'start': 2, 'stop': 5}}
        )
        result = proxy.query_with_params(action_data)

        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]['age'], 2)
        self.assertEqual(result[2]['age'], 4)

    def test_slice_with_stop_only(self):
        """query_with_params() should support slicing with stop only."""
        proxy = GlueQuerySetProxy(
            target=Gorilla.objects.all().order_by('age'),
            unique_name='gorillas',
            access=GlueAccess.VIEW,
        )

        action_data = dto.ActionPayloadSchema(context_data={}, user_data={'slice': {'stop': 3}})
        result = proxy.query_with_params(action_data)

        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]['age'], 0)
        self.assertEqual(result[2]['age'], 2)

    def test_filter_raises_validation_error_for_disallowed_field(self):
        """Should raise GlueQuerySetFilterValidationError when filter references disallowed field."""
        proxy = GlueQuerySetProxy(
            target=Gorilla.objects.all(),
            unique_name='gorillas',
            access=GlueAccess.VIEW,
            fields=['name', 'age'],  # Only name and age allowed
        )

        action_data = dto.ActionPayloadSchema(
            context_data={},
            user_data={'filter': {'weight__gte': 200}},  # weight not in fields
        )

        from django_glue.exceptions import GlueQuerySetFilterValidationError
        with self.assertRaises(GlueQuerySetFilterValidationError) as context:
            proxy.query_with_params(action_data)

        self.assertEqual(context.exception.field, 'weight')
