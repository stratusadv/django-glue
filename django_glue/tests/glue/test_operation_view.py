from __future__ import annotations

import json
import os

import django
from django.test import RequestFactory, TestCase

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_project.settings')
django.setup()

from django_glue.access import GlueAccess
from django_glue.glue import ModelGlue, FunctionGlue
from django_glue.glue.views import glue_attribute_call_view
from django_glue.tests.conftest import MockSession
from test_project.gorilla.models import Gorilla


class GlueAttributeRequestViewTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.session = MockSession(session_key='session-1')
        self.gorilla = Gorilla.objects.create(
            name='Koko',
            description='Leader',
            age=18,
            weight=200.0,
            height=1.8,
        )

    def attribute_request(self, object_name, policy, attribute, kwargs=None, state=None):
        request = self.factory.post(
            f'/__dg__/callable_attribute/{object_name}/',
            data={
                'policy': json.dumps(policy.model_dump(), default=str),
                'attribute': attribute,
                'kwargs': json.dumps(kwargs or {}, default=str),
                **({'state': json.dumps(state, default=str)} if state is not None else {}),
            },
        )
        request.resolver_match = type(
            'ResolverMatch',
            (),
            {'kwargs': {'object_name': object_name}},
        )()
        request.session = self.session
        request.user = 'TestUser'
        return request

    def test_attribute_request_view_saves_model_state(self):
        glue_object = ModelGlue(
            self.gorilla,
            name='gorilla',
            access=GlueAccess.CHANGE,
            fields=['name', 'age', 'weight', 'height'],
        )
        glue_object.request = self.request_context()
        policy = glue_object.policy
        request = self.attribute_request(
            'gorilla',
            policy,
            'save',
            state={
                'name': {'value': 'Updated'},
                'age': {'value': 19},
                'weight': {'value': 210.0},
                'height': {'value': 1.9},
            },
        )

        response = glue_attribute_call_view(request, object_name='gorilla', attribute_name='save')

        self.assertEqual(response.status_code, 200)
        self.gorilla.refresh_from_db()
        self.assertEqual(self.gorilla.name, 'Updated')
        data = json.loads(response.content)
        self.assertIn('policy', data)
        self.assertIn('state', data)
        self.assertIn('metadata', data)
        self.assertEqual(data['result']['success'], True)

    def test_attribute_request_view_enforces_policy_access(self):
        glue_object = ModelGlue(
            self.gorilla,
            name='gorilla',
            access=GlueAccess.VIEW,
            fields=['name'],
        )
        glue_object.request = self.request_context()
        policy = glue_object.policy
        request = self.attribute_request(
            'gorilla',
            policy,
            'save',
            state={'name': {'value': 'Updated'}},
        )

        response = glue_attribute_call_view(request, object_name='gorilla', attribute_name='save')

        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertEqual(data['error']['code'], 'proxy_access_denied')

    def test_attribute_request_view_missing_policy_returns_400(self):
        request = self.factory.post(
            '/__dg__/callable_attribute/gorilla/',
            data={'attribute': 'save'},
        )
        request.resolver_match = type(
            'ResolverMatch',
            (),
            {'kwargs': {'object_name': 'gorilla'}},
        )()
        request.session = self.session

        response = glue_attribute_call_view(request, object_name='gorilla', attribute_name='save')

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertEqual(data['error']['code'], 'missing_policy')

    def test_attribute_request_view_rejects_non_object_kwargs(self):
        glue_object = ModelGlue(
            self.gorilla,
            name='gorilla',
            access=GlueAccess.CHANGE,
            fields=['name'],
        )
        glue_object.request = self.request_context()
        policy = glue_object.policy
        request = self.factory.post(
            '/__dg__/callable_attribute/gorilla/',
            data={
                'policy': json.dumps(policy.model_dump(), default=str),
                'attribute': 'save',
                'kwargs': json.dumps(['not', 'an', 'object']),
            },
        )
        request.resolver_match = type(
            'ResolverMatch',
            (),
            {'kwargs': {'object_name': 'gorilla'}},
        )()
        request.session = self.session

        response = glue_attribute_call_view(request, object_name='gorilla', attribute_name='save')

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertEqual(data['error']['code'], 'invalid_kwargs')

    def test_attribute_request_view_executes_function(self):
        glue_object = FunctionGlue(
            'django_glue.tests.glue.test_operation_view.sample_function',
            name='sample',
            access=GlueAccess.VIEW,
        )
        glue_object.request = self.request_context()
        policy = glue_object.policy
        request = self.attribute_request(
            'sample',
            policy,
            'execute',
            {'kwargs': {'amount': 5, 'tax': 2}},
        )

        response = glue_attribute_call_view(request, object_name='sample', attribute_name='execute')

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['result']['result'], 7)

    def test_attribute_request_view_preserves_consumer_glue_response(self):
        glue_object = ModelGlue(
            self.gorilla,
            name='gorilla',
            access=GlueAccess.DELETE,
            fields=['name'],
        )
        glue_object.request = self.request_context()
        policy = glue_object.policy
        request = self.attribute_request(
            'gorilla',
            policy,
            'battle_cry',
            {'intensity': 'normal'},
        )

        response = glue_attribute_call_view(request, object_name='gorilla', attribute_name='battle_cry')

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['result']['gorilla'], 'Koko')
        self.assertEqual(len(data['messages']), 1)
        self.assertIn('Koko beats their chest!', data['messages'][0]['message'])
        self.assertIn('policy', data)
        self.assertIn('state', data)
        self.assertIn('metadata', data)

    def request_context(self):
        return type('Request', (), {'session': self.session, 'FILES': {}})()


def sample_function(amount: int, tax: int = 0):
    return amount + tax


class GlueInvalidSessionErrorTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.gorilla = Gorilla.objects.create(
            name='Koko',
            description='Leader',
            age=18,
            weight=200.0,
            height=1.8,
        )

    def test_session_mismatch_raises_glue_invalid_session_error(self):
        """Policy with a different session_id raises GlueInvalidSessionError, not GlueInvalidPolicyError."""
        glue_object = ModelGlue(
            self.gorilla,
            name='gorilla',
            access=GlueAccess.CHANGE,
            fields=['name'],
        )
        glue_object.request = self.request_context('matching-session')
        policy = glue_object.policy
        request = self.factory.post(
            '/__dg__/callable_attribute/gorilla/',
            data={
                'policy': json.dumps(policy.model_dump(), default=str),
                'attribute': 'save',
                'kwargs': json.dumps({}),
            },
        )
        request.resolver_match = type(
            'ResolverMatch',
            (),
            {'kwargs': {'object_name': 'gorilla'}},
        )()
        request.session = MockSession(session_key='different-session')

        response = glue_attribute_call_view(request, object_name='gorilla', attribute_name='save')

        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertEqual(data['error']['code'], 'proxy_invalid_session')
        self.assertIn('gorilla', data['error']['message'])
        self.assertIn('session', data['error']['message'].lower())

    def test_session_mismatch_details_include_proxy_name(self):
        """Error details include the proxy name for programmatic access."""
        glue_object = ModelGlue(
            self.gorilla,
            name='my_proxy',
            access=GlueAccess.CHANGE,
            fields=['name'],
        )
        glue_object.request = self.request_context('matching-session')
        policy = glue_object.policy
        request = self.factory.post(
            '/__dg__/callable_attribute/my_proxy/',
            data={
                'policy': json.dumps(policy.model_dump(), default=str),
                'attribute': 'save',
                'kwargs': json.dumps({}),
            },
        )
        request.resolver_match = type(
            'ResolverMatch',
            (),
            {'kwargs': {'object_name': 'my_proxy'}},
        )()
        request.session = MockSession(session_key='different-session')

        response = glue_attribute_call_view(request, object_name='my_proxy', attribute_name='save')

        data = json.loads(response.content)
        self.assertEqual(data['error']['details']['proxy'], 'my_proxy')

    def test_matching_session_allows_request(self):
        """Requests with matching session_id proceed normally."""
        session = MockSession(session_key='same-session')
        glue_object = ModelGlue(
            self.gorilla,
            name='gorilla',
            access=GlueAccess.CHANGE,
            fields=['name'],
        )
        glue_object.request = self.request_context('same-session')
        policy = glue_object.policy
        request = self.factory.post(
            '/__dg__/callable_attribute/gorilla/',
            data={
                'policy': json.dumps(policy.model_dump(), default=str),
                'attribute': 'save',
                'kwargs': json.dumps({}),
            },
        )
        request.resolver_match = type(
            'ResolverMatch',
            (),
            {'kwargs': {'object_name': 'gorilla'}},
        )()
        request.session = session

        response = glue_attribute_call_view(request, object_name='gorilla', attribute_name='save')

        self.assertEqual(response.status_code, 200)

    def request_context(self, session_key):
        return type('Request', (), {'session': MockSession(session_key=session_key), 'FILES': {}})()
