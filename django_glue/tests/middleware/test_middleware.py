"""
Tests for Django Glue middleware (expired proxy cleanup).
"""
from django.test import TestCase, RequestFactory

from django_glue.middleware import DjangoGlueMiddleware
from django_glue.access.access import GlueAccess
from django_glue.proxies.model.proxy import GlueModelProxy
from django_glue.session import GlueSession
from django_glue import settings
from test_project.gorilla.models import Gorilla
from django_glue.tests.conftest import MockSession


class DjangoGlueMiddlewareTestCase(TestCase):
    """Tests for DjangoGlueMiddleware."""

    def setUp(self):
        self.factory = RequestFactory()
        self.gorilla = Gorilla.objects.create(
            name='Test Gorilla',
            description='Test',
            age=25,
            weight=350.0,
            height=1.8
        )
        self.response_called = False

        def get_response(request):
            self.response_called = True
            from django.http import HttpResponse
            return HttpResponse('OK')

        self.middleware = DjangoGlueMiddleware(get_response)

    def test_middleware_calls_get_response(self):
        """Middleware should call the downstream get_response."""
        request = self.factory.get('/')
        request.session = MockSession()

        self.middleware(request)

        self.assertTrue(self.response_called)

    def test_middleware_purges_expired_proxies_on_non_glue_request(self):
        """Middleware should purge expired proxies on non-glue requests."""
        request = self.factory.get('/')
        request.session = MockSession()

        proxy = GlueModelProxy(
            target=self.gorilla,
            unique_name='gorilla',
            access=GlueAccess.VIEW,
        )
        session = GlueSession(request)
        session.register_proxy(proxy)

        # Force expire
        session.keep_live_registry['gorilla'] = 0.0

        self.middleware(request)

        session = GlueSession(request)
        self.assertNotIn('gorilla', session.proxy_registry)

    def test_is_glue_view_request_returns_false_for_unresolved_path(self):
        """_is_glue_view_request should return False when resolve() raises Resolver404."""
        request = self.factory.get('/nonexistent/path/that/raises/Resolver404/')
        result = self.middleware._is_glue_view_request(request)
        self.assertFalse(result)


    def test_middleware_skips_purge_for_action_view(self):
        """Middleware should not purge proxies for action view requests."""
        request = self.factory.post('/__dg__/action/gorilla/get/')
        request.session = MockSession()

        proxy = GlueModelProxy(
            target=self.gorilla,
            unique_name='gorilla',
            access=GlueAccess.VIEW,
        )
        session = GlueSession(request)
        session.register_proxy(proxy)

        # Force expire - should NOT be purged for glue view
        session.keep_live_registry['gorilla'] = 0.0

        self.middleware(request)

        session = GlueSession(request)
        self.assertIn('gorilla', session.proxy_registry)

    def test_middleware_skips_purge_for_keep_live_view(self):
        """Middleware should not purge proxies for keep_live view requests."""
        request = self.factory.post('/__dg__/keep_live/')
        request.session = MockSession()

        proxy = GlueModelProxy(
            target=self.gorilla,
            unique_name='gorilla',
            access=GlueAccess.VIEW,
        )
        session = GlueSession(request)
        session.register_proxy(proxy)

        # Force expire - should NOT be purged for glue view
        session.keep_live_registry['gorilla'] = 0.0

        self.middleware(request)

        session = GlueSession(request)
        self.assertIn('gorilla', session.proxy_registry)
