"""
Tests for GlueViewResolver.
"""
import json
from unittest.mock import patch, MagicMock

from django.http import HttpResponse, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.test import TestCase, RequestFactory

from django_glue.resolver.view.resolver import ViewResolver
from django_glue.resolver.exceptions import GlueResolverError
from django_glue.tests.conftest import MockSession
from django_glue.constants import DJANGO_GLUE_MANIFEST_REQUEST_ATTR_KEY


class GlueViewResolverTestCase(TestCase):
    """Tests for GlueViewResolver."""

    def setUp(self):
        self.factory = RequestFactory()
        self.request = self.factory.post('/')
        self.request.session = MockSession()

    def _build_request(self, url_path, method='POST', view_payload=None):
        """Build a POST request with view body data."""
        body = {
            'url_path': url_path,
            'method': method,
            'view_payload': view_payload or {},
        }
        request = self.factory.post(
            '/',
            data=json.dumps(body),
            content_type='application/json',
        )
        request.session = MockSession()
        return request

    def test_resolves_admin_view_returns_json(self):
        """Should resolve an admin view and return JSON response."""
        request = self._build_request('/admin/')

        resolver = ViewResolver(request)
        response = resolver.resolve()

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn('html', data)
        self.assertIn('manifest_list', data)
        self.assertIsInstance(data['manifest_list'], list)

    def test_handles_http_response(self):
        """Should handle plain HttpResponse and return JSON."""
        request = self._build_request('/admin/')

        resolver = ViewResolver(request)
        response = resolver.resolve()

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn('html', data)

    def test_raises_for_external_redirect(self):
        """Should raise GlueResolverError for external redirects."""
        request = self._build_request('/admin/')

        resolver = ViewResolver(request)

        with self.assertRaises(GlueResolverError) as context:
            resolver.raise_external_redirects_not_supported('https://example.com')

        self.assertEqual(context.exception.response_status, 400)
        self.assertIn('External redirect not supported', context.exception.response_error)

    def test_raises_for_too_many_redirects(self):
        """Should raise GlueResolverError when max redirects exceeded."""
        request = self._build_request('/admin/')

        resolver = ViewResolver(request)

        with self.assertRaises(GlueResolverError) as context:
            resolver.raise_to_many_redirects()

        self.assertEqual(context.exception.response_status, 500)
        self.assertIn('Too many redirects', context.exception.response_error)

    def test_raises_for_unsupported_response_type(self):
        """Should raise GlueResolverError for unsupported response types."""
        request = self._build_request('/admin/')

        resolver = ViewResolver(request)

        class FakeResponse:
            pass

        with self.assertRaises(GlueResolverError) as context:
            resolver.raise_unsupported_response_type(FakeResponse())

        self.assertEqual(context.exception.response_status, 500)
        self.assertIn('Unsupported response type', context.exception.response_error)

    def test_resolve_returns_error_json_for_resolver_error(self):
        """resolve() should catch GlueResolverError and return JSON error."""
        request = self._build_request('/admin/')

        resolver = ViewResolver(request)

        with patch.object(resolver, 'get_response') as mock_get:
            mock_get.side_effect = GlueResolverError(
                response_error='Something went wrong',
                response_status=404,
            )

            response = resolver.resolve()

        self.assertEqual(response.status_code, 404)
        data = json.loads(response.content)
        self.assertIn('error', data)
        self.assertIn('Something went wrong', data['error'])

    def test_glue_view_http_request_property(self):
        """glue_view_http_request should return GlueViewHttpRequest instance."""
        request = self._build_request('/admin/')

        resolver = ViewResolver(request)
        wrapped = resolver.glue_view_http_request

        from django_glue.resolver.view.request import ViewHttpRequest
        self.assertIsInstance(wrapped, ViewHttpRequest)
        self.assertEqual(wrapped.method, 'POST')

    def test_glue_view_http_request_is_reused_for_registered_proxies(self):
        """Registered proxies should be read from the same wrapped request used by the view."""
        request = self._build_request('/admin/')

        resolver = ViewResolver(request)
        wrapped = resolver.glue_view_http_request
        setattr(
            wrapped,
            DJANGO_GLUE_MANIFEST_REQUEST_ATTR_KEY,
            [{'state': {}, 'policy': {'name': 'gorilla'}}],
        )

        self.assertIs(resolver.glue_view_http_request, wrapped)
        self.assertEqual(
            getattr(resolver.glue_view_http_request, DJANGO_GLUE_MANIFEST_REQUEST_ATTR_KEY),
            [{'state': {}, 'policy': {'name': 'gorilla'}}],
        )

    def test_handles_template_response(self):
        """Should handle TemplateResponse and return rendered HTML."""
        request = self._build_request('/admin/')

        resolver = ViewResolver(request)

        mock_template_response = MagicMock(spec=TemplateResponse)
        mock_template_response.content = b'<html><body>Hello</body></html>'

        with patch.object(resolver, 'get_response', return_value=mock_template_response):
            response = resolver.resolve()

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn('Hello', data['html'])

    def test_resolve_catches_external_redirect_error(self):
        """resolve() should catch external redirect GlueResolverError and return JSON."""
        request = self._build_request('/admin/')

        resolver = ViewResolver(request)

        mock_redirect = MagicMock(spec=HttpResponseRedirect)
        mock_redirect.url = 'https://example.com'

        with patch.object(resolver, 'get_response', return_value=mock_redirect):
            response = resolver.resolve()

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn('error', data)
        self.assertIn('External redirect not supported', data['error'])

    def test_resolve_handles_internal_redirect(self):
        """resolve() should follow internal redirects."""
        request = self._build_request('/admin/')

        resolver = ViewResolver(request)

        mock_redirect = MagicMock(spec=HttpResponseRedirect)
        mock_redirect.url = '/admin/'

        mock_response = HttpResponse('<html>OK</html>')

        call_count = [0]
        def side_effect():
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_redirect
            return mock_response

        with patch.object(resolver, 'get_response', side_effect=side_effect):
            with patch('django_glue.resolver.view.resolver.resolve') as mock_resolve:
                from django.urls import ResolverMatch
                mock_match = MagicMock(spec=ResolverMatch)
                mock_match.view_name = 'admin:index'
                mock_resolve.return_value = mock_match

                with patch('django_glue.resolver.view.resolver.reverse', return_value='/admin/'):
                    response = resolver.resolve()

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn('OK', data['html'])

    def test_view_body_is_parsed_from_request(self):
        """Should parse ViewBodySchema from request."""
        request = self._build_request('/admin/', method='GET', view_payload={'key': 'val'})

        resolver = ViewResolver(request)

        self.assertEqual(resolver.view_body.url_path, '/admin/')
        self.assertEqual(resolver.view_body.method, 'GET')
        self.assertEqual(resolver.view_body.view_payload, {'key': 'val'})

    def test_get_response_calls_view_func(self):
        """get_response should call the resolved view function."""
        request = self._build_request('/admin/')

        resolver = ViewResolver(request)

        with patch('django_glue.resolver.view.resolver.resolve') as mock_resolve:
            from django.urls import ResolverMatch
            mock_match = MagicMock(spec=ResolverMatch)
            mock_match.func = MagicMock(return_value=HttpResponse('<html>test</html>'))
            mock_match.kwargs = {}
            mock_resolve.return_value = mock_match

            response = resolver.get_response()

        self.assertEqual(response.content, b'<html>test</html>')
