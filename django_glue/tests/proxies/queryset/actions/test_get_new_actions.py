"""
Tests for Django Glue QuerySetProxy get() and new() actions.
"""
from django.test import TestCase

from django_glue.access.access import GlueAccess
from django_glue.proxies import GlueQuerySetProxy
from django_glue.exceptions import GlueModelInstanceNotFoundError, GlueAccessError
from django_glue.resolver.action.schemas import ActionPayloadSchema
from test_project.gorilla.models import Gorilla


class GlueQuerySetProxyGetTestCase(TestCase):
    """Tests for GlueQuerySetProxy.get() action."""

    def setUp(self):
        self.gorilla1 = Gorilla.objects.create(
            name='Gorilla 1',
            description='First gorilla',
            age=18,
            weight=200.0,
            height=1.8
        )
        self.gorilla2 = Gorilla.objects.create(
            name='Gorilla 2',
            description='Second gorilla',
            age=25,
            weight=250.0,
            height=2.0
        )

    def test_get_returns_model_dict_by_pk(self):
        """get() should return the model instance as a dict for the given pk."""
        proxy = GlueQuerySetProxy(
            target=Gorilla.objects.all(),
            unique_name='gorillas',
            access=GlueAccess.VIEW,
        )

        action_data = ActionPayloadSchema(
            context_data={},
            post_data={'id': self.gorilla1.pk}
        )
        result = proxy.get(action_data)

        self.assertIsInstance(result, dict)
        self.assertEqual(result['name'], 'Gorilla 1')
        self.assertEqual(result['id'], self.gorilla1.pk)

    def test_get_raises_not_found_for_invalid_pk(self):
        """get() should raise GlueModelInstanceNotFoundError for non-existent pk."""
        proxy = GlueQuerySetProxy(
            target=Gorilla.objects.all(),
            unique_name='gorillas',
            access=GlueAccess.VIEW,
        )

        action_data = ActionPayloadSchema(
            context_data={},
            post_data={'id': 99999}
        )

        with self.assertRaises(GlueModelInstanceNotFoundError):
            proxy.get(action_data)

    def test_get_works_with_view_access(self):
        """get() should work with VIEW access level."""
        proxy = GlueQuerySetProxy(
            target=Gorilla.objects.all(),
            unique_name='gorillas',
            access=GlueAccess.VIEW,
        )

        action_data = ActionPayloadSchema(
            context_data={},
            post_data={'id': self.gorilla1.pk}
        )

        result = proxy.process_action('get', action_data)
        self.assertEqual(result['name'], 'Gorilla 1')

    def test_get_works_with_higher_access(self):
        """get() should work with CHANGE and DELETE access levels."""
        for access in [GlueAccess.CHANGE, GlueAccess.DELETE]:
            proxy = GlueQuerySetProxy(
                target=Gorilla.objects.all(),
                unique_name='gorillas',
                access=access,
            )

            action_data = ActionPayloadSchema(
                context_data={},
                post_data={'id': self.gorilla1.pk}
            )
            result = proxy.get(action_data)
            self.assertEqual(result['name'], 'Gorilla 1')


class GlueQuerySetProxyNewTestCase(TestCase):
    """Tests for GlueQuerySetProxy.new() action."""

    def test_new_returns_default_values(self):
        """new() should return default field values for a new instance."""
        proxy = GlueQuerySetProxy(
            target=Gorilla.objects.all(),
            unique_name='gorillas',
            access=GlueAccess.VIEW,
        )

        action_data = ActionPayloadSchema(context_data={})
        result = proxy.new(action_data)

        self.assertIsInstance(result, dict)
        self.assertIsNone(result['id'])

    def test_new_includes_all_form_fields(self):
        """new() should include all form field definitions."""
        proxy = GlueQuerySetProxy(
            target=Gorilla.objects.all(),
            unique_name='gorillas',
            access=GlueAccess.VIEW,
        )

        action_data = ActionPayloadSchema(context_data={})
        result = proxy.new(action_data)

        self.assertIn('name', result)
        self.assertIn('age', result)
        self.assertIn('weight', result)

    def test_new_returns_default_field_values(self):
        """new() should return the model's default values for each field."""
        proxy = GlueQuerySetProxy(
            target=Gorilla.objects.all(),
            unique_name='gorillas',
            access=GlueAccess.VIEW,
        )

        action_data = ActionPayloadSchema(context_data={})
        result = proxy.new(action_data)

        # Gorilla.age has default=18
        self.assertEqual(result['age'], 18)
        # Gorilla.weight has default=200.0
        self.assertEqual(result['weight'], 200.0)
        # Gorilla.height has default=1.8
        self.assertEqual(result['height'], 1.8)
        # Gorilla.rank_points has default=0
        self.assertEqual(result['rank_points'], 0)

    def test_new_m2m_fields_default_to_empty_list(self):
        """new() should return empty list for M2M fields."""
        proxy = GlueQuerySetProxy(
            target=Gorilla.objects.all(),
            unique_name='gorillas',
            access=GlueAccess.VIEW,
        )

        action_data = ActionPayloadSchema(context_data={})
        result = proxy.new(action_data)

        self.assertIn('skills', result)
        self.assertEqual(result['skills'], [])

    def test_new_respects_fields_filter(self):
        """new() should only return fields specified in the fields filter."""
        proxy = GlueQuerySetProxy(
            target=Gorilla.objects.all(),
            unique_name='gorillas',
            access=GlueAccess.VIEW,
            fields=['name', 'age'],
        )

        action_data = ActionPayloadSchema(context_data={})
        result = proxy.new(action_data)

        self.assertIn('name', result)
        self.assertIn('age', result)
        self.assertNotIn('weight', result)
        self.assertNotIn('height', result)

    def test_new_works_with_view_access(self):
        """new() should work with VIEW access level."""
        proxy = GlueQuerySetProxy(
            target=Gorilla.objects.all(),
            unique_name='gorillas',
            access=GlueAccess.VIEW,
        )

        action_data = ActionPayloadSchema(context_data={})
        result = proxy.process_action('new', action_data)

        self.assertIsInstance(result, dict)

    def test_new_works_with_higher_access(self):
        """new() should work with CHANGE and DELETE access levels."""
        for access in [GlueAccess.CHANGE, GlueAccess.DELETE]:
            proxy = GlueQuerySetProxy(
                target=Gorilla.objects.all(),
                unique_name='gorillas',
                access=access,
            )

            action_data = ActionPayloadSchema(context_data={})
            result = proxy.new(action_data)
            self.assertIsInstance(result, dict)

    def test_from_action_request_data_reconstructs_proxy(self):
        """from_action_request_data should reconstruct proxy from encoded query."""
        from django.db.models import QuerySet
        proxy = GlueQuerySetProxy(
            target=Gorilla.objects.all(),
            unique_name='gorillas',
            access=GlueAccess.VIEW,
        )
        encoded = proxy.encoded_query

        reconstructed = GlueQuerySetProxy.from_action_request_data(
            encoded_query=encoded,
            access=GlueAccess.VIEW,
            unique_name='gorillas',
        )

        self.assertIsInstance(reconstructed.target, QuerySet)
        self.assertEqual(reconstructed.target.count(), proxy.target.count())

    def test_get_returns_error_for_missing_pk(self):
        """get() should return error dict when id is missing from post_data."""
        proxy = GlueQuerySetProxy(
            target=Gorilla.objects.all(),
            unique_name='gorillas',
            access=GlueAccess.VIEW,
        )

        action_data = ActionPayloadSchema(context_data={}, post_data={})
        result = proxy.get(action_data)

        self.assertFalse(result['success'])
        self.assertIn('id is required', result['error'])
