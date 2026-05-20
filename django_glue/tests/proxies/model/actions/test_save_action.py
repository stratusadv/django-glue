"""
Tests for Django Glue save() action on ModelProxy.
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_project.settings')
django.setup()

from django.test import TestCase

from django_glue.access.access import GlueAccess
from django_glue.proxies import GlueModelProxy
from django_glue.exceptions import GlueAccessError
from django_glue import data_transfer_objects as dto
from test_project.gorilla.models import Gorilla


class GlueModelProxySaveTestCase(TestCase):
    """Tests for GlueModelProxy.save() action."""

    def setUp(self):
        """Create a test gorilla for each test."""
        self.gorilla = Gorilla.objects.create(
            name='Original Name',
            description='Original description',
            age=18,
            weight=200.0,
            height=1.8,
        )

    def test_save_updates_instance_fields(self):
        """save() action should update model instance fields from payload."""
        proxy = GlueModelProxy(target=self.gorilla, unique_name='gorilla', access=GlueAccess.CHANGE)

        action_data = dto.GlueActionRequestData(
            context_data={},
            post_data={
                'name': 'Updated Name',
                'description': 'Updated description',
                'age': 5,
                'weight': 200.0,
                'height': 1.8,
                'rank_points': 0,
            },
        )
        proxy.save(action_data)

        # Refresh from database
        self.gorilla.refresh_from_db()

        self.assertEqual(self.gorilla.name, 'Updated Name')
        self.assertEqual(self.gorilla.description, 'Updated description')
        self.assertEqual(self.gorilla.age, 5)

    def test_save_persists_to_database(self):
        """save() action should persist changes to the database."""
        proxy = GlueModelProxy(target=self.gorilla, unique_name='gorilla', access=GlueAccess.CHANGE)

        action_data = dto.GlueActionRequestData(
            context_data={},
            post_data={
                'name': 'Persisted Name',
                'description': 'Persisted description',
                'age': 1,
                'weight': 200.0,
                'height': 1.8,
                'rank_points': 0,
            },
        )
        proxy.save(action_data)

        # Fetch fresh from database
        fresh_gorilla = Gorilla.objects.get(pk=self.gorilla.pk)
        self.assertEqual(fresh_gorilla.name, 'Persisted Name')

    def test_save_returns_validation_result(self):
        """save() action should return a validation result dict with success status."""
        proxy = GlueModelProxy(target=self.gorilla, unique_name='gorilla', access=GlueAccess.CHANGE)

        action_data = dto.GlueActionRequestData(
            context_data={},
            post_data={
                'name': 'New Name',
                'description': 'New description',
                'age': 10,
                'weight': 200.0,
                'height': 1.8,
                'rank_points': 0,
            },
        )
        result = proxy.save(action_data)

        self.assertIsInstance(result, dict)
        self.assertIn('success', result)
        self.assertTrue(result['success'])
        self.assertIn('cleaned_data', result)

    def test_save_only_updates_included_fields(self):
        """save() action should ignore payload keys not in _included_fields."""
        proxy = GlueModelProxy(
            target=self.gorilla,
            unique_name='gorilla',
            access=GlueAccess.CHANGE,
            fields=['name'],  # Only these fields are allowed
        )

        action_data = dto.GlueActionRequestData(
            context_data={},
            post_data={
                'name': 'Allowed Update',
                'description': 'Should be ignored',  # Not in fields
                'age': 999,  # Not in fields
            },
        )
        proxy.save(action_data)

        self.gorilla.refresh_from_db()

        self.assertEqual(self.gorilla.name, 'Allowed Update')
        self.assertEqual(self.gorilla.description, 'Original description')  # Unchanged
        self.assertEqual(self.gorilla.age, 18)  # Unchanged

    def test_save_requires_change_access(self):
        """save() action should require at least CHANGE access level."""
        proxy = GlueModelProxy(
            target=self.gorilla,
            unique_name='gorilla',
            access=GlueAccess.VIEW,  # Insufficient access
        )

        action_data = dto.GlueActionRequestData(context_data={}, post_data={'name': 'Should Fail'})

        with self.assertRaises(GlueAccessError):
            proxy.process_action('save', action_data)

    def test_save_works_with_delete_access(self):
        """save() action should work with DELETE access level (cascading)."""
        proxy = GlueModelProxy(target=self.gorilla, unique_name='gorilla', access=GlueAccess.DELETE)

        action_data = dto.GlueActionRequestData(
            context_data={},
            post_data={
                'name': 'Updated with DELETE access',
                'description': 'Description',
                'age': 1,
                'weight': 200.0,
                'height': 1.8,
                'rank_points': 0,
            },
        )
        result = proxy.save(action_data)

        self.assertTrue(result['success'])
