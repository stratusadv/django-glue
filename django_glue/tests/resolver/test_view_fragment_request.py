"""
Tests for ViewFragmentHttpRequest.
"""
import json

from django.test import TestCase, RequestFactory

from django_glue.resolver.view_fragment.request import ViewFragmentHttpRequest


class ViewFragmentHttpRequestTestCase(TestCase):
    """Tests for ViewFragmentHttpRequest wrapper."""

    def setUp(self):
        self.factory = RequestFactory()
        self.base_request = self.factory.get('/')
        self.base_request.session = {}

    def test_sets_method(self):
        """Should set the HTTP method from view request context."""
        req = ViewFragmentHttpRequest(
            base_request=self.base_request,
            method='POST',
            url_path='/some/path/',
            view_payload={'key': 'value'},
        )

        self.assertEqual(req.method, 'POST')

    def test_sets_body_as_json(self):
        """Should encode view_payload as JSON in body."""
        req = ViewFragmentHttpRequest(
            base_request=self.base_request,
            method='POST',
            url_path='/some/path/',
            view_payload={'name': 'test', 'count': 42},
        )

        body = json.loads(req.body.decode('utf-8'))
        self.assertEqual(body, {'name': 'test', 'count': 42})

    def test_sets_content_type(self):
        """Should set content_type to application/json."""
        req = ViewFragmentHttpRequest(
            base_request=self.base_request,
            method='POST',
            url_path='/some/path/',
            view_payload={},
        )

        self.assertEqual(req.content_type, 'application/json')

    def test_sets_path_info(self):
        """Should extract path from url_path."""
        req = ViewFragmentHttpRequest(
            base_request=self.base_request,
            method='GET',
            url_path='/some/path/',
            view_payload={},
        )

        self.assertEqual(req.path_info, '/some/path/')

    def test_parses_query_params_single_value(self):
        """Should parse single-value query params into GET."""
        req = ViewFragmentHttpRequest(
            base_request=self.base_request,
            method='GET',
            url_path='/path/?name=test',
            view_payload={},
        )

        self.assertEqual(req.GET['name'], 'test')

    def test_parses_query_params_multiple_values(self):
        """Should parse multi-value query params into GET as list."""
        req = ViewFragmentHttpRequest(
            base_request=self.base_request,
            method='GET',
            url_path='/path/?tags=a&tags=b',
            view_payload={},
        )

        self.assertEqual(req.GET['tags'], ['a', 'b'])

    def test_delegates_unknown_attributes_to_base(self):
        """Unknown attributes should delegate to the base request."""
        req = ViewFragmentHttpRequest(
            base_request=self.base_request,
            method='GET',
            url_path='/path/',
            view_payload={},
        )

        self.assertEqual(req.session, {})

    def test_empty_view_payload(self):
        """Should handle empty view_payload dict."""
        req = ViewFragmentHttpRequest(
            base_request=self.base_request,
            method='GET',
            url_path='/path/',
            view_payload={},
        )

        body = json.loads(req.body.decode('utf-8'))
        self.assertEqual(body, {})
