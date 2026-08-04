"""
Tests for GlueViewFragmentResolver.
"""
import json
from unittest.mock import patch, MagicMock

from django.http import HttpResponse, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.test import TestCase, RequestFactory

from django_glue.exceptions import GlueRequestError, GlueRequestErrorCode
from django_glue.glue.context import GlueContextManager
from django_glue.tests.conftest import MockSession
from django_glue.resolver.view_fragment.resolver import GlueViewFragmentResolver
from django_glue.resolver.view_fragment.request import ViewFragmentHttpRequest


class GlueViewFragmentResolverTestCase(TestCase):
    """Tests for GlueViewFragmentResolver."""

    def setUp(self):
        self.factory = RequestFactory()
        self.request = self.factory.post('/')
        self.request.session = MockSession()

    def _build_request(self, url_path, method='POST', view_payload=None):
        """Build a POST request with view context data."""
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

    def _build_view(self, request):
        view = GlueViewFragmentResolver()
        view.setup(request)
        return view

    def test_resolves_admin_view_returns_json(self):
        """Should resolve an admin view and return JSON response."""
        request = self._build_request('/admin/')

        response = GlueViewFragmentResolver.as_view()(request)

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn('html', data)
        self.assertIn('manifest_list', data)
        self.assertIsInstance(data['manifest_list'], list)

    def test_handles_http_response(self):
        """Should handle plain HttpResponse and return JSON."""
        request = self._build_request('/admin/')

        response = GlueViewFragmentResolver.as_view()(request)

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn('html', data)

    def test_raises_for_external_redirect(self):
        """Should raise GlueRequestError for external redirects."""
        request = self._build_request('/admin/')

        view = self._build_view(request)

        with self.assertRaises(GlueRequestError) as context:
            view._raise_external_redirects_not_supported('https://example.com')

        self.assertEqual(
            context.exception.code,
            GlueRequestErrorCode.EXTERNAL_VIEW_REDIRECT_NOT_SUPPORTED,
        )
        self.assertEqual(context.exception.status, 400)
        self.assertIn('External redirect not supported', str(context.exception))

    def test_raises_for_too_many_redirects(self):
        """Should raise GlueRequestError when max redirects exceeded."""
        request = self._build_request('/admin/')

        view = self._build_view(request)

        with self.assertRaises(GlueRequestError) as context:
            view._raise_too_many_redirects()

        self.assertEqual(context.exception.code, GlueRequestErrorCode.TOO_MANY_VIEW_REDIRECTS)
        self.assertEqual(context.exception.status, 500)
        self.assertIn('Too many redirects', str(context.exception))

    def test_raises_for_unsupported_response_type(self):
        """Should raise GlueRequestError for unsupported response types."""
        request = self._build_request('/admin/')

        view = self._build_view(request)

        class FakeResponse:
            pass

        with self.assertRaises(GlueRequestError) as context:
            view._raise_unsupported_response_type(FakeResponse())

        self.assertEqual(context.exception.code, GlueRequestErrorCode.UNSUPPORTED_VIEW_RESPONSE_TYPE)
        self.assertEqual(context.exception.status, 500)
        self.assertIn('Unsupported response type', str(context.exception))

    def test_resolve_returns_error_json_for_request_error(self):
        """Should catch GlueRequestError and return JSON error."""
        request = self._build_request('/admin/')

        view = self._build_view(request)

        with patch.object(view, '_call_resolved_view') as mock_get:
            mock_get.side_effect = GlueRequestError(
                code='test_error',
                message='Something went wrong',
                status=404,
            )

            response = view.post(request)

        self.assertEqual(response.status_code, 404)
        data = json.loads(response.content)
        self.assertEqual(data['result']['error']['code'], 'test_error')
        self.assertIn('Something went wrong', data['result']['error']['message'])

    def test_build_glue_view_http_request(self):
        """Should build a ViewFragmentHttpRequest from the request context."""
        request = self._build_request('/admin/')

        view = self._build_view(request)
        context = view._create_context_from_request(request)
        wrapped = view._build_glue_view_http_request(context)
        self.assertIsInstance(wrapped, ViewFragmentHttpRequest)
        self.assertEqual(wrapped.method, 'POST')

    def test_glue_view_http_request_uses_base_request_for_registered_proxies(self):
        """Registered proxies should be stored on the base request."""
        request = self._build_request('/admin/')

        view = self._build_view(request)
        context = view._create_context_from_request(request)
        wrapped = view._build_glue_view_http_request(context)

        self.assertIs(GlueContextManager(wrapped).manifests, GlueContextManager(request).manifests)

    def test_handles_template_response(self):
        """Should handle TemplateResponse and return rendered HTML."""
        request = self._build_request('/admin/')

        view = self._build_view(request)

        mock_template_response = MagicMock(spec=TemplateResponse)
        mock_template_response.content = b'<html><body>Hello</body></html>'

        with patch.object(view, '_call_resolved_view', return_value=mock_template_response):
            response = view.post(request)

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn('Hello', data['html'])

    def test_resolve_catches_external_redirect_error(self):
        """Should catch external redirect errors and return JSON."""
        request = self._build_request('/admin/')

        view = self._build_view(request)

        mock_redirect = MagicMock(spec=HttpResponseRedirect)
        mock_redirect.url = 'https://example.com'

        with patch.object(view, '_call_resolved_view', return_value=mock_redirect):
            response = view.post(request)

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertEqual(
            data['result']['error']['code'],
            GlueRequestErrorCode.EXTERNAL_VIEW_REDIRECT_NOT_SUPPORTED,
        )
        self.assertIn('External redirect not supported', data['result']['error']['message'])

    def test_resolve_handles_internal_redirect(self):
        """resolve() should follow internal redirects."""
        request = self._build_request('/admin/')

        view = self._build_view(request)

        mock_redirect = MagicMock(spec=HttpResponseRedirect)
        mock_redirect.url = '/admin/'

        mock_response = HttpResponse('<html>OK</html>')

        call_count = [0]

        def side_effect(_context):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_redirect
            return mock_response

        with patch.object(view, '_call_resolved_view', side_effect=side_effect):
            with patch('django_glue.resolver.view_fragment.resolver.resolve') as mock_resolve:
                from django.urls import ResolverMatch
                mock_match = MagicMock(spec=ResolverMatch)
                mock_match.view_name = 'admin:index'
                mock_resolve.return_value = mock_match

                with patch(
                    'django_glue.resolver.view_fragment.resolver.reverse',
                    return_value='/admin/',
                ):
                    response = view.post(request)

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn('OK', data['html'])

    def test_context_is_parsed_from_request(self):
        """Should parse ViewFragmentRequestContext from request."""
        request = self._build_request('/admin/', method='GET', view_payload={'key': 'val'})

        view = self._build_view(request)
        context = view._create_context_from_request(request)

        self.assertEqual(context.url_path, '/admin/')
        self.assertEqual(context.method, 'GET')
        self.assertEqual(context.view_payload, {'key': 'val'})

    def test_call_resolved_view_calls_view_func(self):
        """Should call the resolved view function."""
        request = self._build_request('/admin/')

        view = self._build_view(request)
        context = view._create_context_from_request(request)

        with patch('django_glue.resolver.view_fragment.resolver.resolve') as mock_resolve:
            from django.urls import ResolverMatch
            mock_match = MagicMock(spec=ResolverMatch)
            mock_match.func = MagicMock(return_value=HttpResponse('<html>test</html>'))
            mock_match.kwargs = {}
            mock_resolve.return_value = mock_match

            response = view._call_resolved_view(context)

        self.assertEqual(response.content, b'<html>test</html>')
