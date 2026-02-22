"""
Tests for GlueProxyFieldsMixin payload validation methods.
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


class ValidatePayloadFieldTestCase(TestCase):
    """Tests for _validate_payload_field method."""

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

    def test_validates_string_field(self):
        """CharField should accept string values."""
        result = self.proxy._validate_payload_field(
            'title',
            {'type': 'CharField'},
            'New Title'
        )
        self.assertEqual(result, 'New Title')

    def test_validates_boolean_field(self):
        """BooleanField should accept boolean values."""
        result = self.proxy._validate_payload_field(
            'done',
            {'type': 'BooleanField'},
            True
        )
        self.assertEqual(result, True)

    def test_validates_integer_field(self):
        """IntegerField should accept integer values."""
        result = self.proxy._validate_payload_field(
            'order',
            {'type': 'IntegerField'},
            42
        )
        self.assertEqual(result, 42)

    def test_rejects_invalid_string_for_boolean(self):
        """BooleanField should reject string values."""
        with self.assertRaises(GluePayloadValidationError) as ctx:
            self.proxy._validate_payload_field(
                'done',
                {'type': 'BooleanField'},
                'true'
            )
        self.assertEqual(ctx.exception.field, 'done')
        self.assertEqual(ctx.exception.expected_type, 'BooleanField')

    def test_rejects_integer_for_string_field(self):
        """CharField should reject integer values."""
        with self.assertRaises(GluePayloadValidationError) as ctx:
            self.proxy._validate_payload_field(
                'title',
                {'type': 'CharField'},
                123
            )
        self.assertEqual(ctx.exception.field, 'title')

    def test_allows_none_for_nullable_field(self):
        """Nullable fields should accept None."""
        result = self.proxy._validate_payload_field(
            'description',
            {'type': 'TextField', 'null': True},
            None
        )
        self.assertIsNone(result)

    def test_allows_none_for_blank_field(self):
        """Fields with blank=True should accept None."""
        result = self.proxy._validate_payload_field(
            'description',
            {'type': 'TextField', 'blank': True},
            None
        )
        self.assertIsNone(result)

    def test_rejects_none_for_non_nullable_field(self):
        """Non-nullable fields should reject None."""
        with self.assertRaises(GluePayloadValidationError) as ctx:
            self.proxy._validate_payload_field(
                'title',
                {'type': 'CharField', 'null': False},
                None
            )
        self.assertIn('null', ctx.exception.reason)

    def test_allows_unknown_field_types(self):
        """Unknown field types should pass through validation."""
        result = self.proxy._validate_payload_field(
            'custom',
            {'type': 'CustomField'},
            'any value'
        )
        self.assertEqual(result, 'any value')


class ValidatePayloadTestCase(TestCase):
    """Tests for _validate_payload method."""

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

    def test_raises_on_first_invalid_field(self):
        """Should raise GluePayloadValidationError on first invalid field."""
        with self.assertRaises(GluePayloadValidationError):
            self.proxy._validate_payload({
                'title': 'Valid',
                'done': 'invalid',  # Should be boolean
            })

    def test_returns_empty_dict_for_empty_payload(self):
        """Empty payload should return empty dict."""
        result = self.proxy._validate_payload({})
        self.assertEqual(result, {})


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
        with self.assertRaises(GluePayloadValidationError) as ctx:
            proxy.save({'done': 'not a boolean'})

        self.assertEqual(ctx.exception.field, 'done')

        # Verify no changes were made
        self.task.refresh_from_db()
        self.assertEqual(self.task.done, False)

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
