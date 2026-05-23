"""
Tests for Django Glue views (HTTP endpoints).
"""
import json
from unittest.mock import patch

from django.test import TestCase, RequestFactory
from django.http import JsonResponse

from django_glue.views.action_views import action_view
from django_glue.views.keep_live_views import keep_live_view
from django_glue.views.session_data_views import session_data_view
from django_glue.access.access import GlueAccess
from django_glue.proxies.model.proxy import GlueModelProxy
from django_glue.session import GlueSession
from django_glue import settings
from test_project.gorilla.models import Gorilla
from django_glue.tests.conftest import MockSession


class ActionViewTestCase(TestCase):
    """Tests for action_view endpoint."""

    def setUp(self):
        self.factory = RequestFactory()
        self.gorilla = Gorilla.objects.create(
            name='Test Gorilla',
            description='Test',
            age=25,
            weight=350.0,
            height=1.8
        )
        self.request = self.factory.post('/')
        self.request.session = MockSession()
        # Register the proxy
        proxy = GlueModelProxy(
            target=self.gorilla,
            unique_name='gorilla',
            access=GlueAccess.CHANGE,
        )
        GlueSession(self.request).register_proxy(proxy)

    def _build_action_request(self, action, post_data=None):
        """Build a POST request for an action."""
        context_data = {
            'subject_type': 'Model',
            'model_class': 'Gorilla',
            'app_label': 'gorilla',
            'target_pk': self.gorilla.pk,
        }
        body = {
            'context_data': context_data,
            'post_data': post_data or {},
            'file_data': {},
        }
        return self.factory.post(
            f'/__dg__/action/gorilla/{action}/',
            data=json.dumps(body),
            content_type='application/json'
        )

    def test_action_view_returns_json_response(self):
        """action_view should return a JsonResponse."""
        request = self._build_action_request('get')
        request.session = self.request.session

        response = action_view(request, 'gorilla', 'get')

        self.assertIsInstance(response, JsonResponse)
        self.assertEqual(response.status_code, 200)

    def test_action_view_executes_get_action(self):
        """action_view should execute the get action and return data."""
        request = self._build_action_request('get')
        request.session = self.request.session

        response = action_view(request, 'gorilla', 'get')
        data = json.loads(response.content)

        self.assertEqual(data['name'], 'Test Gorilla')

    def test_action_view_executes_save_action(self):
        """action_view should execute the save action and persist changes."""
        post_data = {
            'name': 'Updated Name',
            'description': 'Test',
            'age': 25,
            'weight': 350.0,
            'height': 1.8,
            'rank_points': 0,
        }
        request = self._build_action_request('save', post_data)
        request.session = self.request.session

        response = action_view(request, 'gorilla', 'save')
        data = json.loads(response.content)

        self.assertTrue(data['success'])
        self.gorilla.refresh_from_db()
        self.assertEqual(self.gorilla.name, 'Updated Name')

    def test_action_view_rejects_unsupported_content_type(self):
        """action_view should reject unsupported content types."""
        request = self.factory.post('/__dg__/action/gorilla/get/', content_type='text/plain')

        response = action_view(request, 'gorilla', 'get')

        self.assertEqual(response.status_code, 400)
        self.assertIn('Unsupported media type', response.content.decode())

    def test_action_view_raises_for_missing_proxy(self):
        """action_view should raise GlueProxyNotFoundError for unregistered proxy."""
        request = self.factory.post('/')
        request.session = MockSession()
        body = {
            'context_data': {
                'subject_type': 'Model',
                'model_class': 'Gorilla',
                'app_label': 'gorilla',
                'target_pk': self.gorilla.pk,
            },
            'post_data': {},
            'file_data': {},
        }
        request = self.factory.post(
            '/__dg__/action/nonexistent/get/',
            data=json.dumps(body),
            content_type='application/json'
        )
        request.session = MockSession()

        from django_glue.exceptions import GlueProxyNotFoundError
        with self.assertRaises(GlueProxyNotFoundError):
            action_view(request, 'nonexistent', 'get')


class KeepLiveViewTestCase(TestCase):
    """Tests for keep_live_view endpoint."""

    def setUp(self):
        self.factory = RequestFactory()
        self.gorilla = Gorilla.objects.create(
            name='Test Gorilla',
            description='Test',
            age=25,
            weight=350.0,
            height=1.8
        )
        self.request = self.factory.post('/')
        self.request.session = MockSession()
        proxy = GlueModelProxy(
            target=self.gorilla,
            unique_name='gorilla',
            access=GlueAccess.VIEW,
        )
        GlueSession(self.request).register_proxy(proxy)

    def test_keep_live_returns_proxy_registry(self):
        """keep_live_view should return the proxy registry."""
        body = json.dumps({'unique_names': ['gorilla']})
        request = self.factory.post(
            '/__dg__/keep_live/',
            data=body,
            content_type='application/json'
        )
        request.session = self.request.session

        response = keep_live_view(request)
        data = json.loads(response.content)

        self.assertIn('gorilla', data)
        self.assertEqual(data['gorilla'], GlueAccess.VIEW)

    def test_keep_live_renews_proxy_expiration(self):
        """keep_live_view should renew proxy expiration time."""
        glue_session = GlueSession(self.request)
        old_expire = glue_session.keep_live_registry['gorilla']

        body = json.dumps({'unique_names': ['gorilla']})
        request = self.factory.post(
            '/__dg__/keep_live/',
            data=body,
            content_type='application/json'
        )
        request.session = self.request.session

        keep_live_view(request)
        glue_session = GlueSession(self.request)
        new_expire = glue_session.keep_live_registry['gorilla']

        self.assertGreater(new_expire, old_expire)

    def test_keep_live_with_empty_names(self):
        """keep_live_view should handle empty unique_names gracefully."""
        body = json.dumps({'unique_names': []})
        request = self.factory.post(
            '/__dg__/keep_live/',
            data=body,
            content_type='application/json'
        )
        request.session = self.request.session

        response = keep_live_view(request)
        self.assertEqual(response.status_code, 200)


class SessionDataViewTestCase(TestCase):
    """Tests for session_data_view endpoint."""

    def setUp(self):
        self.factory = RequestFactory()
        self.gorilla = Gorilla.objects.create(
            name='Test Gorilla',
            description='Test',
            age=25,
            weight=350.0,
            height=1.8
        )
        self.request = self.factory.get('/')
        self.request.session = MockSession()
        proxy = GlueModelProxy(
            target=self.gorilla,
            unique_name='gorilla',
            access=GlueAccess.VIEW,
        )
        GlueSession(self.request).register_proxy(proxy)

    def test_session_data_returns_registry(self):
        """session_data_view should return the proxy registry."""
        request = self.factory.get('/__dg__/session_data/')
        request.session = self.request.session

        response = session_data_view(request)
        data = json.loads(response.content)

        self.assertIn('gorilla', data)

    def test_session_data_returns_empty_for_no_proxies(self):
        """session_data_view should return empty dict when no proxies registered."""
        request = self.factory.get('/__dg__/session_data/')
        request.session = MockSession()

        response = session_data_view(request)
        data = json.loads(response.content)

        self.assertEqual(data, {})
