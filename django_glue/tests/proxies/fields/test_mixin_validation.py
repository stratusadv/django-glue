"""
Tests for GlueProxyModelFieldsMixin payload validation methods.

Validation is now handled by Django's modelform_factory, which provides
full Django form validation including max_length, choices, custom validators, etc.
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_project.settings')
django.setup()

from django.test import TestCase

from django_glue.access.access import GlueAccess
from django_glue.proxies import GlueModelProxy
from django_glue.resolver.action import schemas as dto
from test_project.gorilla.models import Gorilla


class ValidatePayloadTestCase(TestCase):
    """Tests for payload validation using form validation."""

    def setUp(self):
        self.gorilla = Gorilla.objects.create(
            name='Test Gorilla', description='Test description', age=18, weight=200.0, height=1.8
        )
        self.proxy = GlueModelProxy(
            target=self.gorilla, unique_name='gorilla', access=GlueAccess.CHANGE
        )

    def test_validates_all_fields(self):
        """Should validate all fields in payload."""
        action_data = dto.ActionPayloadSchema(
            context_data={},
            user_data={
                'name': 'Updated Name',
                'description': 'Test description',
                'age': 5,
                'weight': 200.0,
                'height': 1.8,
                'rank_points': 0,
            },
        )
        result = self.proxy.validate(action_data)

        self.assertTrue(result['success'])
        self.assertEqual(result['cleaned_data']['name'], 'Updated Name')
        self.assertEqual(result['cleaned_data']['age'], 5)

    def test_filters_out_non_included_fields(self):
        """Fields not in fields list should not be validated/returned."""
        proxy = GlueModelProxy(
            target=self.gorilla,
            unique_name='gorilla',
            access=GlueAccess.CHANGE,
            fields=['name', 'age'],  # Only these fields
        )
        action_data = dto.ActionPayloadSchema(
            context_data={},
            user_data={
                'name': 'Updated',
                'age': 10,
                'description': 'Should be ignored',  # Not in fields
                'weight': 999,  # Not in fields
            },
        )
        result = proxy.validate(action_data)

        self.assertTrue(result['success'])
        self.assertIn('name', result['cleaned_data'])
        self.assertIn('age', result['cleaned_data'])
        self.assertNotIn('description', result['cleaned_data'])
        self.assertNotIn('weight', result['cleaned_data'])

    def test_returns_empty_cleaned_data_for_invalid_payload(self):
        """Invalid payload should return empty cleaned_data."""
        action_data = dto.ActionPayloadSchema(
            context_data={},
            user_data={
                'name': ''  # Required field is empty
            },
        )
        result = self.proxy.validate(action_data)

        self.assertFalse(result['success'])
        self.assertEqual(result['cleaned_data'], {})

    def test_returns_errors_on_invalid_field_value(self):
        """Should return errors on invalid field value."""
        action_data = dto.ActionPayloadSchema(
            context_data={},
            user_data={
                'name': '',  # CharField is required
                'age': 1,
            },
        )
        result = self.proxy.validate(action_data)

        self.assertFalse(result['success'])
        self.assertIn('name', result['errors'])

    def test_cleans_data_types(self):
        """Form validation should clean/coerce data types."""
        action_data = dto.ActionPayloadSchema(
            context_data={},
            user_data={
                'name': 'Test Gorilla',
                'description': '',
                'age': '42',  # String should be coerced to int
                'weight': 200.0,
                'height': 1.8,
                'rank_points': 0,
            },
        )
        result = self.proxy.validate(action_data)

        self.assertTrue(result['success'])
        self.assertEqual(result['cleaned_data']['age'], 42)
        self.assertIsInstance(result['cleaned_data']['age'], int)

    def test_validates_max_length(self):
        """Should validate max_length constraints from model field."""
        # Gorilla.name has max_length=255, so 260 chars should fail
        long_name = 'x' * 260
        action_data = dto.ActionPayloadSchema(
            context_data={},
            user_data={
                'name': long_name,
                'age': 1,
                'weight': 200.0,
                'height': 1.8,
                'rank_points': 0,
            },
        )
        result = self.proxy.validate(action_data)

        self.assertFalse(result['success'])
        self.assertIn('name', result['errors'])

    def test_validates_min_value(self):
        """Should validate MinValueValidator on integer field."""
        # Gorilla.age has MinValueValidator(1), so 0 should fail
        action_data = dto.ActionPayloadSchema(
            context_data={},
            user_data={'name': 'Test', 'age': 0, 'weight': 200.0, 'height': 1.8, 'rank_points': 0},
        )
        result = self.proxy.validate(action_data)

        self.assertFalse(result['success'])
        self.assertIn('age', result['errors'])

    def test_validates_max_value(self):
        """Should validate MaxValueValidator on integer field."""
        # Gorilla.age has MaxValueValidator(60), so 61 should fail
        action_data = dto.ActionPayloadSchema(
            context_data={},
            user_data={'name': 'Test', 'age': 61, 'weight': 200.0, 'height': 1.8, 'rank_points': 0},
        )
        result = self.proxy.validate(action_data)

        self.assertFalse(result['success'])
        self.assertIn('age', result['errors'])

    def test_allows_blank_field(self):
        """Should accept empty string for fields with blank=True."""
        # Gorilla.description has blank=True
        action_data = dto.ActionPayloadSchema(
            context_data={},
            user_data={
                'name': 'Test',
                'description': '',
                'age': 1,
                'weight': 200.0,
                'height': 1.8,
                'rank_points': 0,
            },
        )
        result = self.proxy.validate(action_data)

        self.assertTrue(result['success'])
        self.assertEqual(result['cleaned_data']['description'], '')


class SaveActionValidationIntegrationTestCase(TestCase):
    """Integration tests for validation in save() action."""

    def setUp(self):
        self.gorilla = Gorilla.objects.create(
            name='Test Gorilla', description='Test description', age=18, weight=200.0, height=1.8
        )

    def test_save_validates_payload(self):
        """save() should validate payload before applying changes."""
        proxy = GlueModelProxy(target=self.gorilla, unique_name='gorilla', access=GlueAccess.CHANGE)
        # Empty name should fail validation
        action_data = dto.ActionPayloadSchema(
            context_data={},
            user_data={
                'name': '',  # Required field empty
                'age': 1,
                'weight': 200.0,
                'height': 1.8,
                'rank_points': 0,
            },
        )
        result = proxy.save(action_data)

        self.assertFalse(result['success'])
        self.assertIn('name', result['errors'])

        # Verify no changes were made
        self.gorilla.refresh_from_db()
        self.assertEqual(self.gorilla.name, 'Test Gorilla')

    def test_save_succeeds_with_valid_payload(self):
        """save() should succeed with valid payload."""
        proxy = GlueModelProxy(target=self.gorilla, unique_name='gorilla', access=GlueAccess.CHANGE)
        action_data = dto.ActionPayloadSchema(
            context_data={},
            user_data={
                'name': 'Updated Name',
                'description': 'Test description',
                'age': 1,
                'weight': 200.0,
                'height': 1.8,
                'rank_points': 0,
            },
        )
        result = proxy.save(action_data)

        self.assertTrue(result['success'])
        self.assertEqual(result['cleaned_data']['name'], 'Updated Name')

        self.gorilla.refresh_from_db()
        self.assertEqual(self.gorilla.name, 'Updated Name')
