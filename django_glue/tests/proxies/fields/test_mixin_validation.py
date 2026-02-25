"""
Tests for GlueProxyModelFieldsMixin payload validation methods.

Validation is now handled by Django's modelform_factory, which provides
full Django form validation including max_length, choices, custom validators, etc.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_project.base_settings')
django.setup()

from django.test import TestCase

from django_glue.access.access import GlueAccess
from django_glue.proxies.model.proxy import GlueModelProxy
from django_glue.exceptions import GluePayloadValidationError
from test_project.task.models import Task


class ValidatePayloadTestCase(TestCase):
    """Tests for _validate_payload method using modelform_factory."""

    def setUp(self):
        self.task = Task.objects.create(
            title='Test Task',
            description='Test description',
            done=False,
            order=1
        )
        self.proxy = GlueModelProxy(
            target=self.task,
            unique_name='task',
            access=GlueAccess.CHANGE,
        )

    def test_validates_all_fields(self):
        """Should validate all fields in payload."""
        result = self.proxy._validate_payload({
            'title': 'Updated Title',
            'done': True,
            'order': 5
        })
        self.assertEqual(result['title'], 'Updated Title')
        self.assertEqual(result['done'], True)
        self.assertEqual(result['order'], 5)

    def test_filters_out_non_included_fields(self):
        """Fields not in _included_fields should be filtered out."""
        proxy = GlueModelProxy(
            target=self.task,
            unique_name='task',
            access=GlueAccess.CHANGE,
            fields=['title', 'done'],  # Only these fields
        )
        result = proxy._validate_payload({
            'title': 'Updated',
            'description': 'Should be ignored',  # Not in fields
            'order': 999,  # Not in fields
        })
        self.assertIn('title', result)
        self.assertNotIn('description', result)
        self.assertNotIn('order', result)

    def test_returns_empty_dict_for_empty_payload(self):
        """Empty payload should return empty dict."""
        result = self.proxy._validate_payload({})
        self.assertEqual(result, {})

    def test_raises_on_invalid_field_value(self):
        """Should raise GluePayloadValidationError on invalid field value."""
        # CharField can't accept None (required field)
        with self.assertRaises(GluePayloadValidationError) as ctx:
            self.proxy._validate_payload({
                'title': None,  # CharField is required
            })
        self.assertEqual(ctx.exception.field, 'title')

    def test_cleans_data_types(self):
        """ModelForm validation should clean/coerce data types."""
        result = self.proxy._validate_payload({
            'order': '42',  # String should be coerced to int
        })
        self.assertEqual(result['order'], 42)
        self.assertIsInstance(result['order'], int)

    def test_validates_max_length(self):
        """Should validate max_length constraints from model field."""
        # Task.title has max_length=50, so 60 chars should fail
        long_title = 'x' * 60
        with self.assertRaises(GluePayloadValidationError) as ctx:
            self.proxy._validate_payload({
                'title': long_title,
            })
        self.assertEqual(ctx.exception.field, 'title')
        self.assertIn('50', ctx.exception.reason)  # Should mention the limit

    def test_validates_min_value(self):
        """Should validate MinValueValidator on integer field."""
        # Task.order has MinValueValidator(1), so 0 should fail
        with self.assertRaises(GluePayloadValidationError) as ctx:
            self.proxy._validate_payload({
                'order': 0,
            })
        self.assertEqual(ctx.exception.field, 'order')

    def test_validates_max_value(self):
        """Should validate MaxValueValidator on integer field."""
        # Task.order has MaxValueValidator(1000), so 1001 should fail
        with self.assertRaises(GluePayloadValidationError) as ctx:
            self.proxy._validate_payload({
                'order': 1001,
            })
        self.assertEqual(ctx.exception.field, 'order')

    def test_allows_blank_field(self):
        """Should accept empty string for fields with blank=True."""
        # Task.description has blank=True
        result = self.proxy._validate_payload({
            'description': '',
        })
        self.assertEqual(result['description'], '')


class SaveActionValidationIntegrationTestCase(TestCase):
    """Integration tests for validation in save() action."""

    def setUp(self):
        self.task = Task.objects.create(
            title='Test Task',
            description='Test description',
            done=False,
            order=1
        )

    def test_save_validates_payload(self):
        """save() should validate payload before applying changes."""
        proxy = GlueModelProxy(
            target=self.task,
            unique_name='task',
            access=GlueAccess.CHANGE,
        )
        # CharField with None should fail validation
        with self.assertRaises(GluePayloadValidationError) as ctx:
            proxy.save({'title': None})

        self.assertEqual(ctx.exception.field, 'title')

        # Verify no changes were made
        self.task.refresh_from_db()
        self.assertEqual(self.task.title, 'Test Task')

    def test_save_succeeds_with_valid_payload(self):
        """save() should succeed with valid payload."""
        proxy = GlueModelProxy(
            target=self.task,
            unique_name='task',
            access=GlueAccess.CHANGE,
        )
        result = proxy.save({
            'title': 'Updated Title',
            'done': True,
        })

        self.assertEqual(result['title'], 'Updated Title')
        self.assertEqual(result['done'], True)

        self.task.refresh_from_db()
        self.assertEqual(self.task.title, 'Updated Title')
        self.assertEqual(self.task.done, True)