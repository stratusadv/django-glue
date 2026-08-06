"""
Tests for Django Glue custom exceptions.
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_project.settings')
django.setup()

from django.test import TestCase

from django_glue.exceptions import (
    GlueError,
    GlueRequestError,
    GlueAccessError,
    GlueInvalidAttributeError,
    GlueMissingAttributeError,
    GlueModelInstanceNotFoundError,
    GlueQuerySetFilterValidationError,
)


class GlueExceptionsTestCase(TestCase):
    """Tests for custom exception classes."""

    def test_all_exceptions_inherit_from_glue_error(self):
        """All custom exceptions should inherit from GlueError."""
        exception_classes = [
            GlueRequestError,
            GlueAccessError,
            GlueInvalidAttributeError,
            GlueMissingAttributeError,
            GlueModelInstanceNotFoundError,
            GlueQuerySetFilterValidationError,
        ]
        for exc_class in exception_classes:
            self.assertTrue(
                issubclass(exc_class, GlueError),
                f'{exc_class.__name__} should inherit from GlueError',
            )

    def test_glue_request_error(self):
        """GlueRequestError should support precise codes, statuses, and details."""
        exc = GlueRequestError(
            code='missing_policy',
            message='"policy" is required',
            details={'field': 'policy'},
        )

        self.assertEqual(exc.code, 'missing_policy')
        self.assertEqual(exc.status, 400)
        self.assertEqual(exc.details(), {'field': 'policy'})

    def test_glue_access_error(self):
        """GlueAccessError should contain attribute, required_access, and current_access."""
        exc = GlueAccessError(attribute='save', required_access='CHANGE', current_access='VIEW')

        self.assertEqual(exc.attribute, 'save')
        self.assertEqual(exc.required_access, 'CHANGE')
        self.assertEqual(exc.current_access, 'VIEW')
        self.assertEqual(exc.status, 403)
        self.assertEqual(exc.details()['attribute'], 'save')
        self.assertIn('save', str(exc))
        self.assertIn('CHANGE', str(exc))
        self.assertIn('VIEW', str(exc))

    def test_glue_missing_attribute_error(self):
        """GlueMissingAttributeError should contain attribute, proxy_name, and optional reason."""
        exc = GlueMissingAttributeError(
            attribute='unknown_attribute', proxy_name='my_proxy', reason='Method does not exist'
        )

        self.assertEqual(exc.attribute, 'unknown_attribute')
        self.assertEqual(exc.proxy_name, 'my_proxy')
        self.assertEqual(exc.reason, 'Method does not exist')
        self.assertEqual(exc.status, 404)
        self.assertEqual(exc.details()['reason'], 'Method does not exist')
        self.assertIn('unknown_attribute', str(exc))
        self.assertIn('my_proxy', str(exc))

    def test_glue_invalid_attribute_configuration_error(self):
        exc = GlueInvalidAttributeError(
            attribute='services',
            owner='app.models.Domain',
            value_type='app.services.DomainService',
        )

        self.assertEqual(exc.attribute, 'services')
        self.assertEqual(exc.owner, 'app.models.Domain')
        self.assertEqual(exc.value_type, 'app.services.DomainService')
        self.assertEqual(exc.status, 500)
        self.assertEqual(exc.details()['attribute'], 'services')
        self.assertIn('Glue.attribute', str(exc))
        self.assertIn('nested Glue attributes', str(exc))

    def test_glue_missing_attribute_error_without_reason(self):
        """GlueMissingAttributeError should work without a reason."""
        exc = GlueMissingAttributeError(attribute='unknown_attribute', proxy_name='my_proxy')

        self.assertIsNone(exc.reason)
        self.assertIn('unknown_attribute', str(exc))

    def test_glue_model_instance_not_found_error(self):
        """GlueModelInstanceNotFoundError should contain model_name and pk."""
        exc = GlueModelInstanceNotFoundError(model_name='Task', pk=999)

        self.assertEqual(exc.model_name, 'Task')
        self.assertEqual(exc.pk, 999)
        self.assertEqual(exc.status, 404)
        self.assertEqual(exc.details(), {'model': 'Task', 'pk': 999})
        self.assertIn('Task', str(exc))
        self.assertIn('999', str(exc))

    def test_glue_queryset_filter_validation_error(self):
        """GlueQuerySetFilterValidationError should contain field and allowed_fields."""
        exc = GlueQuerySetFilterValidationError(
            field='password', allowed_fields=['id', 'title', 'done']
        )

        self.assertEqual(exc.field, 'password')
        self.assertEqual(exc.allowed_fields, ['id', 'title', 'done'])
        self.assertEqual(exc.status, 422)
        self.assertEqual(exc.details()['field'], 'password')
        self.assertIn('password', str(exc))
        self.assertIn('id', str(exc))
