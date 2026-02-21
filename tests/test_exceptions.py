"""
Tests for Django Glue custom exceptions.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_project.base_settings')
django.setup()

from django.test import TestCase

from django_glue.exceptions import (
    GlueError,
    GlueProxyNotFoundError,
    GlueAccessError,
    GlueMissingActionError,
    GlueModelInstanceNotFoundError,
    GlueQuerySetFilterValidationError,
)


class GlueExceptionsTestCase(TestCase):
    """Tests for custom exception classes."""

    def test_all_exceptions_inherit_from_glue_error(self):
        """All custom exceptions should inherit from GlueError."""
        exception_classes = [
            GlueProxyNotFoundError,
            GlueAccessError,
            GlueMissingActionError,
            GlueModelInstanceNotFoundError,
            GlueQuerySetFilterValidationError,
        ]
        for exc_class in exception_classes:
            self.assertTrue(
                issubclass(exc_class, GlueError),
                f"{exc_class.__name__} should inherit from GlueError"
            )

    def test_glue_proxy_not_found_error(self):
        """GlueProxyNotFoundError should contain unique_name and clear message."""
        exc = GlueProxyNotFoundError('my_task')

        self.assertEqual(exc.unique_name, 'my_task')
        self.assertIn('my_task', str(exc))
        self.assertIn('not found', str(exc).lower())

    def test_glue_access_error(self):
        """GlueAccessError should contain action, required_access, and current_access."""
        exc = GlueAccessError(
            action='save',
            required_access='CHANGE',
            current_access='VIEW'
        )

        self.assertEqual(exc.action, 'save')
        self.assertEqual(exc.required_access, 'CHANGE')
        self.assertEqual(exc.current_access, 'VIEW')
        self.assertIn('save', str(exc))
        self.assertIn('CHANGE', str(exc))
        self.assertIn('VIEW', str(exc))

    def test_glue_missing_action_error(self):
        """GlueMissingActionError should contain action, proxy_name, and optional reason."""
        exc = GlueMissingActionError(
            action='unknown_action',
            proxy_name='my_proxy',
            reason='Method does not exist'
        )

        self.assertEqual(exc.action, 'unknown_action')
        self.assertEqual(exc.proxy_name, 'my_proxy')
        self.assertEqual(exc.reason, 'Method does not exist')
        self.assertIn('unknown_action', str(exc))
        self.assertIn('my_proxy', str(exc))

    def test_glue_missing_action_error_without_reason(self):
        """GlueMissingActionError should work without a reason."""
        exc = GlueMissingActionError(
            action='unknown_action',
            proxy_name='my_proxy'
        )

        self.assertIsNone(exc.reason)
        self.assertIn('unknown_action', str(exc))

    def test_glue_model_instance_not_found_error(self):
        """GlueModelInstanceNotFoundError should contain model_name and pk."""
        exc = GlueModelInstanceNotFoundError(
            model_name='Task',
            pk=999
        )

        self.assertEqual(exc.model_name, 'Task')
        self.assertEqual(exc.pk, 999)
        self.assertIn('Task', str(exc))
        self.assertIn('999', str(exc))

    def test_glue_queryset_filter_validation_error(self):
        """GlueQuerySetFilterValidationError should contain field and allowed_fields."""
        exc = GlueQuerySetFilterValidationError(
            field='password',
            allowed_fields=['id', 'title', 'done']
        )

        self.assertEqual(exc.field, 'password')
        self.assertEqual(exc.allowed_fields, ['id', 'title', 'done'])
        self.assertIn('password', str(exc))
        self.assertIn('id', str(exc))