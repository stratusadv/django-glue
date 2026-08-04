"""
Tests for ViewFragmentRequestContext.
"""
import json

from django.test import TestCase, RequestFactory

from django_glue.exceptions import GlueRequestError, GlueRequestErrorCode
from django_glue.resolver.view_fragment.context import ViewFragmentRequestContext


class ViewFragmentRequestContextTestCase(TestCase):
    """Tests for ViewFragmentRequestContext Pydantic model."""

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

        schema = ViewFragmentRequestContext.from_request(request)

        self.assertEqual(schema.method, 'POST')

    def test_defaults_view_payload(self):
        """Should default view_payload to dict."""
        schema = ViewFragmentRequestContext(url_path='/admin/')

        self.assertEqual(schema.view_payload, {})

    def test_accepts_url_path(self):
        """Should accept url_path directly."""
        schema = ViewFragmentRequestContext(url_path='/admin/')

        self.assertEqual(schema.url_path, '/admin/')

    def test_raises_when_both_url_name_and_url_path_missing(self):
        """Should raise GlueRequestError when neither url_name nor url_path is provided."""
        with self.assertRaises(GlueRequestError) as context:
            ViewFragmentRequestContext()

        self.assertEqual(context.exception.code, GlueRequestErrorCode.MISSING_VIEW_TARGET)
        self.assertEqual(context.exception.status, 400)
        self.assertIn('Missing url_name or url_path', str(context.exception))

    def test_raises_when_url_name_cannot_be_resolved(self):
        """Should raise coded GlueRequestError when url_name cannot be resolved."""
        with self.assertRaises(GlueRequestError) as context:
            ViewFragmentRequestContext(url_name='not-a-real-view')

        self.assertEqual(context.exception.code, GlueRequestErrorCode.VIEW_URL_NAME_NOT_FOUND)
        self.assertEqual(context.exception.status, 404)
        self.assertIn('Could not resolve URL name', str(context.exception))

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

        schema = ViewFragmentRequestContext.from_request(request)

        self.assertEqual(schema.url_path, '/admin/')
        self.assertEqual(schema.method, 'GET')
        self.assertEqual(schema.view_payload, {'key': 'value'})

    def test_allows_extra_fields(self):
        """Schema should allow extra fields via model_config."""
        schema = ViewFragmentRequestContext(url_path='/admin/', extra_field='extra_value')

        self.assertEqual(schema.extra_field, 'extra_value')

    def test_accepts_method_override(self):
        """Should accept custom method."""
        schema = ViewFragmentRequestContext(url_path='/admin/', method='GET')

        self.assertEqual(schema.method, 'GET')

    def test_accepts_view_payload(self):
        """Should accept view_payload dict."""
        schema = ViewFragmentRequestContext(url_path='/admin/', view_payload={'foo': 'bar'})

        self.assertEqual(schema.view_payload, {'foo': 'bar'})
