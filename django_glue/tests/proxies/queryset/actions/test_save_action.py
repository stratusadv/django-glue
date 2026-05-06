"""
Tests for Django Glue save() action on QuerySetProxy.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_project.settings')
django.setup()

from django.test import TestCase

from django_glue.access.access import GlueAccess
from django_glue.proxies import GlueQuerySetProxy
from django_glue.exceptions import GlueAccessError, GlueModelInstanceNotFoundError
from django_glue import data_transfer_objects as dto
from test_project.gorilla.models import Gorilla


class GlueQuerySetProxySaveTestCase(TestCase):
    """Tests for GlueQuerySetProxy.save() action."""

    def setUp(self):
        """Create test gorillas for each test."""
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

    def test_save_updates_specific_instance_by_pk(self):
        """save() action should update the specific instance identified by id in payload."""
        proxy = GlueQuerySetProxy(
            target=Gorilla.objects.all(),
            unique_name='gorillas',
            access=GlueAccess.CHANGE,
        )

        action_data = dto.GlueActionRequestData(
            context_data={},
            post_data={
                'id': self.gorilla1.pk,
                'name': 'Updated Gorilla 1',
                'description': 'First gorilla',
                'age': 18,
                'weight': 200.0,
                'height': 1.8,
                'rank_points': 0,
            }
        )
        proxy.save(action_data)

        self.gorilla1.refresh_from_db()
        self.gorilla2.refresh_from_db()

        self.assertEqual(self.gorilla1.name, 'Updated Gorilla 1')
        self.assertEqual(self.gorilla2.name, 'Gorilla 2')  # Unchanged

    def test_save_returns_validation_result(self):
        """save() action should return a validation result dict with success status."""
        proxy = GlueQuerySetProxy(
            target=Gorilla.objects.all(),
            unique_name='gorillas',
            access=GlueAccess.CHANGE,
        )

        action_data = dto.GlueActionRequestData(
            context_data={},
            post_data={
                'id': self.gorilla1.pk,
                'name': 'New Name',
                'description': 'First gorilla',
                'age': 18,
                'weight': 200.0,
                'height': 1.8,
                'rank_points': 0,
            }
        )
        result = proxy.save(action_data)

        self.assertIsInstance(result, dict)
        self.assertIn('success', result)
        self.assertTrue(result['success'])
        self.assertIn('cleaned_data', result)
        self.assertEqual(result['cleaned_data']['name'], 'New Name')

    def test_save_raises_not_found_for_invalid_pk(self):
        """save() action should raise GlueModelInstanceNotFoundError for non-existent id."""
        proxy = GlueQuerySetProxy(
            target=Gorilla.objects.all(),
            unique_name='gorillas',
            access=GlueAccess.CHANGE,
        )

        action_data = dto.GlueActionRequestData(
            context_data={},
            post_data={
                'id': 99999,
                'name': 'Should Fail',
                'description': 'Test',
                'age': 18,
                'weight': 200.0,
                'height': 1.8,
                'rank_points': 0,
            }
        )

        with self.assertRaises(GlueModelInstanceNotFoundError):
            proxy.save(action_data)

    def test_save_requires_change_access(self):
        """save() action should require at least CHANGE access level."""
        proxy = GlueQuerySetProxy(
            target=Gorilla.objects.all(),
            unique_name='gorillas',
            access=GlueAccess.VIEW,  # Insufficient access
        )

        action_data = dto.GlueActionRequestData(
            context_data={},
            post_data={
                'id': self.gorilla1.pk,
                'name': 'Should Fail',
                'description': 'Test',
                'age': 18,
                'weight': 200.0,
                'height': 1.8,
                'rank_points': 0,
            }
        )

        with self.assertRaises(GlueAccessError):
            proxy.process_action('save', action_data)

    def test_save_works_with_delete_access(self):
        """save() action should work with DELETE access level (cascading)."""
        proxy = GlueQuerySetProxy(
            target=Gorilla.objects.all(),
            unique_name='gorillas',
            access=GlueAccess.DELETE,
        )

        action_data = dto.GlueActionRequestData(
            context_data={},
            post_data={
                'id': self.gorilla1.pk,
                'name': 'Updated with DELETE access',
                'description': 'First gorilla',
                'age': 18,
                'weight': 200.0,
                'height': 1.8,
                'rank_points': 0,
            }
        )
        result = proxy.save(action_data)

        self.assertTrue(result['success'])
        self.assertEqual(result['cleaned_data']['name'], 'Updated with DELETE access')

    def test_save_creates_new_instance_without_id(self):
        """save() action should create a new instance when no id is provided."""
        initial_count = Gorilla.objects.count()

        proxy = GlueQuerySetProxy(
            target=Gorilla.objects.all(),
            unique_name='gorillas',
            access=GlueAccess.CHANGE,
        )

        action_data = dto.GlueActionRequestData(
            context_data={},
            post_data={
                'name': 'New Gorilla',
                'description': 'Created via save',
                'age': 10,
                'weight': 150.0,
                'height': 1.5,
                'rank_points': 0,
            }
        )
        result = proxy.save(action_data)

        self.assertTrue(result['success'])
        self.assertEqual(Gorilla.objects.count(), initial_count + 1)
        self.assertEqual(result['cleaned_data']['name'], 'New Gorilla')
