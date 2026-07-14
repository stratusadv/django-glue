import json
import os
import django
from datetime import timedelta
from unittest.mock import patch

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_project.settings')
django.setup()

from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone
from django_glue.constants import DJANGO_GLUE_PROXIES_REQUEST_ATTR_KEY
from django_glue.tests.conftest import MockSession
from django_glue.tests.proxies.model.helpers import make_model_proxy
from django_glue.tests.proxies.queryset.helpers import make_queryset_proxy
from django_glue.exceptions import GlueBoundAttributeCallError
from django_glue.views.attribute_event_views import _error_response, proxy_bound_attribute_event_view
from test_project.gorilla.models import Gorilla, Skill


class AttributeEventViewTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.gorilla = Gorilla.objects.create(
            name='Test Gorilla',
            description='Test',
            age=18,
            weight=200.0,
            height=1.8,
        )
        self.skill_1 = Skill.objects.create(name='Punch')
        self.skill_2 = Skill.objects.create(name='Kick')

    def _queryset_policy(self, access):
        registration_request = self.factory.get('/')
        registration_request.session = MockSession(session_key='session-1')
        proxy = make_queryset_proxy(Gorilla.objects.all(), access=access)
        proxy._register_with_request(registration_request)
        return registration_request.__dict__[DJANGO_GLUE_PROXIES_REQUEST_ATTR_KEY]['gorillas']['policy']

    def test_proxy_bound_attribute_event_view_insufficient_access_returns_403(self):
        # Create a policy with VIEW access
        policy = self._queryset_policy(access='view')
        
        # Try to invoke 'delete' which requires DELETE access
        request = self.factory.post(
            '/__dg__/bound_attribute_event/gorillas/GlueQuerySetProxy.delete/',
            data={'policy': json.dumps(policy)},
        )
        
        # Set resolver_match kwargs for pydantic validation
        request.resolver_match = type(
            'ResolverMatch',
            (),
            {'kwargs': {'proxy_name': 'gorillas', 'attribute_name': 'GlueQuerySetProxy.delete'}},
        )()
        request.session = MockSession(session_key='session-1')
        
        # Invoke the view directly
        response = proxy_bound_attribute_event_view(
            request,
            proxy_name='gorillas',
            attribute_name='GlueQuerySetProxy.delete',
        )
        
        # Assert response status code is 403 Forbidden
        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertEqual(data['error']['code'], 'proxy_access_denied')
        self.assertEqual(data['error']['status'], 403)
        self.assertEqual(data['error']['details']['attribute'], 'delete')
        self.assertIn("Insufficient access to access 'delete'", data['error']['message'])

    def test_proxy_bound_attribute_event_view_missing_policy_returns_400(self):
        request = self.factory.post(
            '/__dg__/bound_attribute_event/gorillas/GlueQuerySetProxy.delete/',
            data={},
        )
        request.resolver_match = type(
            'ResolverMatch',
            (),
            {'kwargs': {'proxy_name': 'gorillas', 'attribute_name': 'GlueQuerySetProxy.delete'}},
        )()
        request.session = MockSession(session_key='session-1')

        response = proxy_bound_attribute_event_view(
            request,
            proxy_name='gorillas',
            attribute_name='GlueQuerySetProxy.delete',
        )

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertEqual(data['error']['code'], 'missing_policy')
        self.assertEqual(data['error']['status'], 400)

    def test_proxy_bound_attribute_event_view_missing_attribute_returns_404(self):
        policy = self._queryset_policy(access='view')
        request = self.factory.post(
            '/__dg__/bound_attribute_event/gorillas/not_in_policy/',
            data={'policy': json.dumps(policy)},
        )
        request.resolver_match = type(
            'ResolverMatch',
            (),
            {'kwargs': {'proxy_name': 'gorillas', 'attribute_name': 'not_in_policy'}},
        )()
        request.session = MockSession(session_key='session-1')

        response = proxy_bound_attribute_event_view(
            request,
            proxy_name='gorillas',
            attribute_name='not_in_policy',
        )

        self.assertEqual(response.status_code, 404)
        data = json.loads(response.content)
        self.assertEqual(data['error']['code'], 'missing_attribute')
        self.assertEqual(data['error']['details']['attribute'], 'not_in_policy')

    @override_settings(DJANGO_GLUE_PROXY_POLICY_MAX_AGE_SECONDS=60)
    def test_proxy_bound_attribute_event_view_expired_policy_returns_419(self):
        stale_now = timezone.now() - timedelta(seconds=61)
        with patch('django_glue.proxies.policy.timezone.now', return_value=stale_now):
            policy = self._queryset_policy(access='view')

        request = self.factory.post(
            '/__dg__/bound_attribute_event/gorillas/GlueQuerySetProxy.new/',
            data={'policy': json.dumps(policy)},
        )
        request.resolver_match = type(
            'ResolverMatch',
            (),
            {'kwargs': {'proxy_name': 'gorillas', 'attribute_name': 'GlueQuerySetProxy.new'}},
        )()
        request.session = MockSession(session_key='session-1')

        response = proxy_bound_attribute_event_view(
            request,
            proxy_name='gorillas',
            attribute_name='GlueQuerySetProxy.new',
        )

        self.assertEqual(response.status_code, 419)
        data = json.loads(response.content)
        self.assertEqual(data['error']['code'], 'proxy_policy_expired')
        self.assertEqual(data['error']['status'], 419)

    def test_foreign_key_choices_returns_json_array_result(self):
        registration_request = self.factory.get('/')
        registration_request.session = MockSession(session_key='session-1')
        proxy = make_model_proxy(self.gorilla, name='gorilla', access='view')
        proxy._register_with_request(registration_request)
        proxy_data = registration_request.__dict__[DJANGO_GLUE_PROXIES_REQUEST_ATTR_KEY]['gorilla']
        original_signature = proxy_data['policy']['original_signature']
        refreshed_now = timezone.now() + timedelta(seconds=30)

        request = self.factory.post(
            '/__dg__/bound_attribute_event/gorilla/GlueModelInstanceProxy.foreign_key_choices/',
            data={
                'policy': json.dumps(proxy_data['policy']),
                'state': json.dumps(proxy_data['state']),
                'event_kwargs': json.dumps({'field_name': 'skills'}),
            },
        )
        request.resolver_match = type(
            'ResolverMatch',
            (),
            {
                'kwargs': {
                    'proxy_name': 'gorilla',
                    'attribute_name': 'GlueModelInstanceProxy.foreign_key_choices',
                }
            },
        )()
        request.session = MockSession(session_key='session-1')

        with patch('django_glue.proxies.policy.timezone.now', return_value=refreshed_now):
            response = proxy_bound_attribute_event_view(
                request,
                proxy_name='gorilla',
                attribute_name='GlueModelInstanceProxy.foreign_key_choices',
            )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(
            data['result'],
            [
                {'pk': self.skill_1.pk, '__str__': 'Punch'},
                {'pk': self.skill_2.pk, '__str__': 'Kick'},
            ],
        )
        self.assertEqual(data['policy']['created_at'], refreshed_now.timestamp())
        self.assertNotEqual(data['policy']['original_signature'], original_signature)

    def test_decorated_nested_descriptor_attribute_is_exposed_without_glue_meta(self):
        registration_request = self.factory.get('/')
        registration_request.session = MockSession(session_key='session-1')
        proxy = make_model_proxy(self.gorilla, name='gorilla', access='change')
        proxy._register_with_request(registration_request)
        proxy_data = registration_request.__dict__[DJANGO_GLUE_PROXIES_REQUEST_ATTR_KEY]['gorilla']

        self.assertIn('Gorilla.services.increment_age', proxy_data['policy']['bound_attributes'])

        request = self.factory.post(
            '/__dg__/bound_attribute_event/gorilla/Gorilla.services.increment_age/',
            data={
                'policy': json.dumps(proxy_data['policy']),
                'state': json.dumps(proxy_data['state']),
            },
        )
        request.resolver_match = type(
            'ResolverMatch',
            (),
            {
                'kwargs': {
                    'proxy_name': 'gorilla',
                    'attribute_name': 'Gorilla.services.increment_age',
                }
            },
        )()
        request.session = MockSession(session_key='session-1')

        response = proxy_bound_attribute_event_view(
            request,
            proxy_name='gorilla',
            attribute_name='Gorilla.services.increment_age',
        )

        self.assertEqual(response.status_code, 200)
        self.gorilla.refresh_from_db()
        self.assertEqual(self.gorilla.age, 19)

    @override_settings(DEBUG=False)
    def test_internal_attribute_errors_are_sanitized_when_debug_is_disabled(self):
        def broken_attribute(request):
            raise RuntimeError('database credentials leaked')

        error = GlueBoundAttributeCallError(
            callable_attr=broken_attribute,
            original_error=RuntimeError('database credentials leaked'),
            provided_kwargs=['request'],
        )

        response = _error_response(error)

        self.assertEqual(response.status_code, 500)
        data = json.loads(response.content)
        self.assertEqual(data['error']['code'], 'bound_attribute_call_error')
        self.assertEqual(data['error']['message'], 'An unexpected Glue server error occurred.')
        self.assertEqual(data['error']['details'], {})

    @override_settings(DEBUG=True)
    def test_internal_attribute_errors_include_details_when_debug_is_enabled(self):
        def broken_attribute(request):
            raise RuntimeError('debug details available')

        error = GlueBoundAttributeCallError(
            callable_attr=broken_attribute,
            original_error=RuntimeError('debug details available'),
            provided_kwargs=['request'],
        )

        response = _error_response(error)

        self.assertEqual(response.status_code, 500)
        data = json.loads(response.content)
        self.assertIn('debug details available', data['error']['message'])
        self.assertEqual(data['error']['details']['original_error'], 'debug details available')

    @override_settings(DEBUG=False)
    def test_internal_attribute_errors_are_logged_on_the_backend(self):
        policy = self._queryset_policy(access='view')

        request = self.factory.post(
            '/__dg__/bound_attribute_event/gorillas/GlueQuerySetProxy.new/',
            data={'policy': json.dumps(policy)},
        )
        request.resolver_match = type(
            'ResolverMatch',
            (),
            {'kwargs': {'proxy_name': 'gorillas', 'attribute_name': 'GlueQuerySetProxy.new'}},
        )()
        request.session = MockSession(session_key='session-1')

        def broken_attribute(request):
            raise RuntimeError('backend-only details')

        error = GlueBoundAttributeCallError(
            callable_attr=broken_attribute,
            original_error=RuntimeError('backend-only details'),
            provided_kwargs=['request'],
        )

        with (
            patch('django_glue.views.attribute_event_views.ProxyBoundAttributeEventResolver.resolve', side_effect=error),
            patch('django_glue.views.attribute_event_views.logger.exception') as log_exception,
        ):
            response = proxy_bound_attribute_event_view(
                request,
                proxy_name='gorillas',
                attribute_name='GlueQuerySetProxy.new',
            )

        self.assertEqual(response.status_code, 500)
        data = json.loads(response.content)
        self.assertEqual(data['error']['message'], 'An unexpected Glue server error occurred.')
        log_exception.assert_called_once()
