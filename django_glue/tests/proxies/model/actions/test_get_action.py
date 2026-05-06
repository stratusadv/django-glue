"""
Tests for Django Glue get() action on ModelProxy.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_project.settings')
django.setup()

from django.test import TestCase

from django_glue.access.access import GlueAccess
from django_glue.proxies import GlueModelProxy
from django_glue import data_transfer_objects as dto
from test_project.gorilla.models import Gorilla


class GlueModelProxyGetTestCase(TestCase):
    """Tests for GlueModelProxy.get() action."""

    def setUp(self):
        """Create a test gorilla for each test."""
        self.gorilla = Gorilla.objects.create(name='Test Gorilla', description='A gorilla for testing', age=25, weight=350.0, height=1.8)

    def test_get_returns_model_as_dict(self):
        """get() action should return the model instance as a dictionary."""
        proxy = GlueModelProxy(
            target=self.gorilla,
            unique_name='gorilla',
            access=GlueAccess.VIEW,
        )

        action_data = dto.GlueActionRequestData(context_data={})
        result = proxy.get(action_data)

        self.assertIsInstance(result, dict)
        self.assertEqual(result['name'], 'Test Gorilla')
        self.assertEqual(result['description'], 'A gorilla for testing')
        self.assertEqual(result['age'], 25)

    def test_get_includes_id_field(self):
        """get() action should include the id field."""
        proxy = GlueModelProxy(
            target=self.gorilla,
            unique_name='gorilla',
            access=GlueAccess.VIEW,
        )

        action_data = dto.GlueActionRequestData(context_data={})
        result = proxy.get(action_data)

        self.assertIn('id', result)
        self.assertEqual(result['id'], self.gorilla.pk)

    def test_get_respects_fields_filter(self):
        """get() action should only include specified fields when fields parameter is used."""
        proxy = GlueModelProxy(
            target=self.gorilla,
            unique_name='gorilla',
            access=GlueAccess.VIEW,
            fields=['name', 'age'],
        )

        action_data = dto.GlueActionRequestData(context_data={})
        result = proxy.get(action_data)

        self.assertIn('name', result)
        self.assertIn('age', result)
        self.assertNotIn('description', result)
        self.assertNotIn('weight', result)

    def test_get_respects_exclude_filter(self):
        """get() action should exclude specified fields when exclude parameter is used."""
        proxy = GlueModelProxy(
            target=self.gorilla,
            unique_name='gorilla',
            access=GlueAccess.VIEW,
            exclude=['description', 'age'],
        )

        action_data = dto.GlueActionRequestData(context_data={})
        result = proxy.get(action_data)

        self.assertIn('name', result)
        self.assertIn('weight', result)
        self.assertNotIn('description', result)
        self.assertNotIn('age', result)

    def test_get_works_with_view_access(self):
        """get() action should work with VIEW access level."""
        proxy = GlueModelProxy(
            target=self.gorilla,
            unique_name='gorilla',
            access=GlueAccess.VIEW,
        )

        action_data = dto.GlueActionRequestData(context_data={})

        # Should not raise
        result = proxy.process_action('get', action_data)
        self.assertIsNotNone(result)

    def test_get_works_with_higher_access_levels(self):
        """get() action should work with CHANGE and DELETE access levels."""
        for access in [GlueAccess.CHANGE, GlueAccess.DELETE]:
            proxy = GlueModelProxy(
                target=self.gorilla,
                unique_name='gorilla',
                access=access,
            )

            action_data = dto.GlueActionRequestData(context_data={})
            result = proxy.get(action_data)
            self.assertEqual(result['name'], 'Test Gorilla')
