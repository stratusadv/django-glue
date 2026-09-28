from __future__ import annotations

import json
import os

import django
from django.test import RequestFactory, TestCase

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_project.settings')
django.setup()

from django_glue.access import GlueAccess
from django_glue.glue import ModelGlue, FunctionGlue
from django_glue.glue.policy import GluePolicy
from django_glue.resolver.attribute_call.resolver import GlueAttributeCallResolver
from django_glue.tests.conftest import MockSession
from test_project.gorilla.models import Gorilla

glue_attribute_call_view = GlueAttributeCallResolver.as_view()


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

    def attribute_request(self, object_name, policy, attribute, kwargs=None, updates=None):
        entry = {
            'address': policy.address,
            'policy_token': policy.token,
            'call': {'attribute': attribute, 'kwargs': kwargs or {}},
        }
        if updates is not None:
            entry['updates'] = updates
        request = self.factory.post(
            '/__dg__/callable_attribute/',
            data={'objects': json.dumps([entry], default=str)},
        )
        request.session = self.session
        request.user = 'TestUser'
        return request

    @staticmethod
    def entry(response):
        return json.loads(response.content)['objects'][0]

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
            updates={
                'name': 'Updated',
                'age': 19,
                'weight': 210.0,
                'height': 1.9,
            },
        )

        response = glue_attribute_call_view(request)

        self.assertEqual(response.status_code, 200)
        self.gorilla.refresh_from_db()
        self.assertEqual(self.gorilla.name, 'Updated')
        data = self.entry(response)
        self.assertIn('policy_token', data)
        self.assertIn('computed_data', data)
        self.assertNotIn('static_data', data)
        self.assertEqual(data['result']['success'], True)
        successor = GluePolicy.from_token(data['policy_token'])
        self.assertEqual(
            successor.state_snapshot,
            {'name': 'Updated', 'age': 19, 'weight': 210.0, 'height': 1.9},
        )

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
            updates={'name': 'Updated'},
        )

        response = glue_attribute_call_view(request)

        self.assertEqual(response.status_code, 200)
        data = self.entry(response)
        self.assertEqual(data['error']['code'], 'not_authorized')
        self.assertNotIn('policy_token', data)

    def test_attribute_request_view_rejects_policy_for_different_user(self):
        glue_object = ModelGlue(
            self.gorilla,
            name='gorilla',
            access=GlueAccess.CHANGE,
            fields=['name'],
        )
        glue_object.request = self.request_context()
        glue_object.request.user = type('User', (), {'id': 1})()
        policy = glue_object.policy
        request = self.attribute_request(
            'gorilla',
            policy,
            'save',
            updates={'name': 'Updated'},
        )
        request.user = type('User', (), {'id': 2})()

        response = glue_attribute_call_view(request)

        self.assertEqual(response.status_code, 200)
        data = self.entry(response)
        self.assertEqual(data['error']['code'], 'proxy_invalid_user')

    def test_attribute_request_view_missing_objects_returns_400(self):
        request = self.factory.post(
            '/__dg__/callable_attribute/',
            data={'attribute': 'save'},
        )
        request.session = self.session

        response = glue_attribute_call_view(request)

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertEqual(data['result']['error']['code'], 'missing_field')
        self.assertNotIn('objects', data)

    def test_attribute_request_view_rejects_non_object_kwargs(self):
        glue_object = ModelGlue(
            self.gorilla,
            name='gorilla',
            access=GlueAccess.CHANGE,
            fields=['name'],
        )
        glue_object.request = self.request_context()
        policy = glue_object.policy
        entry = {
            'address': policy.address,
            'policy_token': policy.token,
            'call': {'attribute': 'save', 'kwargs': ['not', 'an', 'object']},
        }
        request = self.factory.post(
            '/__dg__/callable_attribute/',
            data={'objects': json.dumps([entry])},
        )
        request.session = self.session

        response = glue_attribute_call_view(request)

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertEqual(data['result']['error']['code'], 'malformed_request')
        self.assertNotIn('objects', data)

    def test_attribute_request_view_duplicate_addresses_fail_the_request(self):
        glue_object = ModelGlue(
            self.gorilla,
            name='gorilla',
            access=GlueAccess.CHANGE,
            fields=['name'],
        )
        glue_object.request = self.request_context()
        policy = glue_object.policy
        entry = {
            'address': policy.address,
            'policy_token': policy.token,
            'call': {'attribute': 'save', 'kwargs': {}},
        }
        request = self.factory.post(
            '/__dg__/callable_attribute/',
            data={'objects': json.dumps([entry, dict(entry)])},
        )
        request.session = self.session
        request.user = 'TestUser'

        response = glue_attribute_call_view(request)

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertEqual(data['result']['error']['code'], 'duplicate_addresses')

    def test_attribute_request_view_address_mismatch_fails_the_request(self):
        glue_object = ModelGlue(
            self.gorilla,
            name='gorilla',
            access=GlueAccess.CHANGE,
            fields=['name'],
        )
        glue_object.request = self.request_context()
        policy = glue_object.policy
        entry = {
            'address': 'some#other-address',
            'policy_token': policy.token,
            'call': {'attribute': 'save', 'kwargs': {}},
        }
        request = self.factory.post(
            '/__dg__/callable_attribute/',
            data={'objects': json.dumps([entry])},
        )
        request.session = self.session
        request.user = 'TestUser'

        response = glue_attribute_call_view(request)

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertEqual(data['result']['error']['code'], 'address_mismatch')

    def test_batch_with_one_failed_entry_advances_every_other_entry(self):
        """Independence invariant (state-model.md §10): a batch with one
        authorization-denied entry advances every other entry as if it had
        travelled alone."""
        first = ModelGlue(
            self.gorilla,
            name='gorilla',
            access=GlueAccess.CHANGE,
            fields=['name'],
        )
        first.request = self.request_context()
        first_policy = first.policy

        denied = ModelGlue(
            self.gorilla,
            name='denied',
            access=GlueAccess.VIEW,
            fields=['name'],
        )
        denied.request = self.request_context()
        denied_policy = denied.policy

        entries = [
            {
                'address': first_policy.address,
                'policy_token': first_policy.token,
                'call': {'attribute': 'save', 'kwargs': {}},
                'updates': {'name': 'Batched'},
            },
            {
                'address': denied_policy.address,
                'policy_token': denied_policy.token,
                'call': {'attribute': 'save', 'kwargs': {}},
                'updates': {'name': 'Hacked'},
            },
        ]
        request = self.factory.post(
            '/__dg__/callable_attribute/',
            data={'objects': json.dumps(entries)},
        )
        request.session = self.session
        request.user = 'TestUser'

        response = glue_attribute_call_view(request)

        self.assertEqual(response.status_code, 200)
        objects = json.loads(response.content)['objects']
        self.assertEqual([item['address'] for item in objects], [
            first_policy.address,
            denied_policy.address,
        ])
        advanced = objects[0]
        self.assertEqual(advanced['result']['success'], True)
        self.assertIn('policy_token', advanced)
        self.assertNotIn('error', advanced)
        failed = objects[1]
        self.assertEqual(failed['error']['code'], 'not_authorized')
        self.assertNotIn('policy_token', failed)
        self.assertNotIn('result', failed)
        self.gorilla.refresh_from_db()
        self.assertEqual(self.gorilla.name, 'Batched')

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

        response = glue_attribute_call_view(request)

        self.assertEqual(response.status_code, 200)
        data = self.entry(response)
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

        response = glue_attribute_call_view(request)

        self.assertEqual(response.status_code, 200)
        data = self.entry(response)
        self.assertEqual(data['result']['gorilla'], 'Koko')
        self.assertEqual(len(data['effects']['messages']), 1)
        self.assertIn('Koko beats their chest!', data['effects']['messages'][0]['message'])
        self.assertNotIn('policy_token', data)
        self.assertNotIn('static_data', data)
        self.assertNotIn('computed_data', data)

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

    def session_request(self, glue_object, session):
        entry = {
            'address': glue_object.policy.address,
            'policy_token': glue_object.policy.token,
            'call': {'attribute': 'save', 'kwargs': {}},
        }
        request = self.factory.post(
            '/__dg__/callable_attribute/',
            data={'objects': json.dumps([entry])},
        )
        request.session = session
        request.user = 'TestUser'
        return request

    def test_session_mismatch_fails_the_entry(self):
        """Policy with a different session_id produces a per-entry error,
        not a whole-response failure."""
        glue_object = ModelGlue(
            self.gorilla,
            name='gorilla',
            access=GlueAccess.CHANGE,
            fields=['name'],
        )
        glue_object.request = self.request_context('matching-session')
        request = self.session_request(
            glue_object,
            MockSession(session_key='different-session'),
        )

        response = glue_attribute_call_view(request)

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)['objects'][0]
        self.assertEqual(data['error']['code'], 'proxy_invalid_session')
        self.assertIn('gorilla', data['error']['message'])
        self.assertIn('session', data['error']['message'].lower())

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
        request = self.session_request(glue_object, session)

        response = glue_attribute_call_view(request)

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)['objects'][0]
        self.assertNotIn('error', data)

    def request_context(self, session_key):
        return type('Request', (), {'session': MockSession(session_key=session_key), 'FILES': {}})()
