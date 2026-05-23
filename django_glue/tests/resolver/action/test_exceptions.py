"""
Tests for GlueResolverError.
"""
from django.test import TestCase

from django_glue.exceptions import GlueError
from django_glue.resolver.exceptions import GlueResolverError


class GlueResolverErrorTestCase(TestCase):
    def test_inherits_from_glue_error(self):
        """GlueResolverError should inherit from GlueError."""
        self.assertTrue(issubclass(GlueResolverError, GlueError))

    def test_stores_response_error(self):
        """Should store response_error attribute."""
        exc = GlueResolverError(response_error='Something went wrong', response_status=500)

        self.assertEqual(exc.response_error, 'Something went wrong')

    def test_stores_response_status(self):
        """Should store response_status attribute."""
        exc = GlueResolverError(response_error='Not found', response_status=404)

        self.assertEqual(exc.response_status, 404)

    def test_message_contains_error(self):
        """Exception message should contain the error string."""
        exc = GlueResolverError(response_error='View not found', response_status=404)

        self.assertIn('View not found', str(exc))
