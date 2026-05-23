"""
Tests for ViewBodySchema.
"""
import json

from django.test import TestCase, RequestFactory

from django_glue.resolver.view.schemas import ViewBodySchema
from django_glue.resolver.exceptions import GlueResolverError


class ViewBodySchemaTestCase(TestCase):
    """Tests for ViewBodySchema Pydantic model."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_defaults_method_to_post(self):
        """Should default method to POST."""
        body = {'url_path': '/admin/'}
        request = self.factory.post(
            '/',
            data=json.dumps(body),
            content_type='application/json',
        )

        schema = ViewBodySchema.from_request(request)

        self.assertEqual(schema.method, 'POST')

    def test_defaults_view_payload(self):
        """Should default view_payload to dict class."""
        schema = ViewBodySchema(url_path='/admin/')

        self.assertEqual(schema.view_payload, dict)

    def test_accepts_url_path(self):
        """Should accept url_path directly."""
        schema = ViewBodySchema(url_path='/admin/')

        self.assertEqual(schema.url_path, '/admin/')

    def test_raises_when_both_url_name_and_url_path_missing(self):
        """Should raise GlueResolverError when neither url_name nor url_path is provided."""
        with self.assertRaises(GlueResolverError) as context:
            ViewBodySchema()

        self.assertEqual(context.exception.response_status, 400)
        self.assertIn('Missing url_name or url_path', context.exception.response_error)

    def test_from_request_parses_json_body(self):
        """from_request should parse JSON body correctly."""
        body = {
            'url_path': '/admin/',
            'method': 'GET',
            'view_payload': {'key': 'value'},
        }
        request = self.factory.post(
            '/',
            data=json.dumps(body),
            content_type='application/json',
        )

        schema = ViewBodySchema.from_request(request)

        self.assertEqual(schema.url_path, '/admin/')
        self.assertEqual(schema.method, 'GET')
        self.assertEqual(schema.view_payload, {'key': 'value'})

    def test_allows_extra_fields(self):
        """Schema should allow extra fields via model_config."""
        schema = ViewBodySchema(url_path='/admin/', extra_field='extra_value')

        self.assertEqual(schema.extra_field, 'extra_value')

    def test_accepts_method_override(self):
        """Should accept custom method."""
        schema = ViewBodySchema(url_path='/admin/', method='GET')

        self.assertEqual(schema.method, 'GET')

    def test_accepts_view_payload(self):
        """Should accept view_payload dict."""
        schema = ViewBodySchema(url_path='/admin/', view_payload={'foo': 'bar'})

        self.assertEqual(schema.view_payload, {'foo': 'bar'})
