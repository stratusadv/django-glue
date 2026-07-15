from django.test import RequestFactory, TestCase

from django_glue.access.access import GlueAccess
from django_glue.constants import DJANGO_GLUE_PROXIES_REQUEST_ATTR_KEY
from django_glue.proxies.policy import ProxyPolicy
from django_glue.proxies.model.instance.proxy import GlueModelInstanceProxy
from django_glue.proxies.queryset.proxy import GlueQuerySetProxy
from django_glue.tests.conftest import MockSession
from test_project.gorilla.models import Gorilla


def make_model_proxy(model, name='gorilla', access=GlueAccess.VIEW):
    state, _, included_field_names = GlueModelInstanceProxy._build_state(model)
    proxy = GlueModelInstanceProxy(name=name, namespace='model', access=access, state=state)
    proxy._policy_included_field_names = included_field_names
    return proxy


class BaseGlueProxyInitTestCase(TestCase):
    def setUp(self):
        self.gorilla = Gorilla.objects.create(
            name='Test Gorilla',
            description='Test',
            age=25,
            weight=350.0,
            height=1.8,
        )

    def test_stores_identity_and_state(self):
        proxy = make_model_proxy(self.gorilla, name='my_gorilla', access=GlueAccess.CHANGE)

        self.assertEqual(proxy.name, 'my_gorilla')
        self.assertEqual(proxy.namespace, 'model')
        self.assertEqual(proxy.access, GlueAccess.CHANGE)
        self.assertIs(proxy.state.model, self.gorilla)

    def test_from_attribute_event_reconstructs_proxy_state(self):
        state, form_class_path, included_field_names = GlueModelInstanceProxy._build_state(self.gorilla)
        proxy = GlueModelInstanceProxy(name='gorilla', namespace='model', access=GlueAccess.VIEW, state=state)
        proxy._form_class_path = form_class_path
        proxy._policy_included_field_names = included_field_names
        request = RequestFactory().get('/')
        request.session = MockSession(session_key='session-1')
        proxy._register_with_request(request)
        registered = getattr(request, DJANGO_GLUE_PROXIES_REQUEST_ATTR_KEY)['gorilla']
        subject_details = {'form_class_path': None, **registered['policy']['subject_details']}

        class Event:
            policy = type('Policy', (), {
                'name': 'gorilla',
                'namespace': 'model',
                'session_id': registered['policy']['session_id'],
                'access': GlueAccess.VIEW,
                'subject_details': type('SubjectDetails', (), subject_details)(),
            })()
            proxy_state = registered['state']
            request = type('Request', (), {'FILES': {}})()

        reconstructed = GlueModelInstanceProxy._from_attribute_event(Event())

        self.assertEqual(reconstructed.name, 'gorilla')
        self.assertEqual(reconstructed.state.model.pk, self.gorilla.pk)


class BaseGlueProxyBoundAttributesTestCase(TestCase):
    def setUp(self):
        self.gorilla = Gorilla.objects.create(
            name='Test Gorilla',
            description='Test',
            age=25,
            weight=350.0,
            height=1.8,
        )

    def test_discovers_bound_attributes_on_proxy_and_targets(self):
        proxy = make_model_proxy(self.gorilla)

        bound_attributes = proxy.discover_bound_attributes()

        self.assertIn('GlueModelInstanceProxy.get', bound_attributes)
        self.assertIn('GlueModelInstanceProxy.save', bound_attributes)
        self.assertIn('GlueModelInstanceProxy.delete', bound_attributes)
        self.assertIn('Gorilla.battle_cry', bound_attributes)

    def test_get_bound_attribute_owner_returns_matching_target(self):
        proxy = make_model_proxy(self.gorilla)
        bound_attribute = proxy.discover_bound_attributes()['Gorilla.battle_cry']

        self.assertIs(proxy._get_bound_attribute_owner(bound_attribute), self.gorilla)

    def test_policy_data_only_includes_attributes_with_available_owner(self):
        proxy = make_model_proxy(self.gorilla)

        policy_data = proxy._policy_data

        self.assertIn('GlueModelInstanceProxy.get', policy_data)
        self.assertIn('Gorilla.battle_cry', policy_data)

    def test_register_with_request_stores_state_and_signed_policy(self):
        proxy = make_model_proxy(self.gorilla)
        request = RequestFactory().get('/')
        request.session = MockSession(session_key=None)

        proxy._register_with_request(request)

        registered = getattr(request, DJANGO_GLUE_PROXIES_REQUEST_ATTR_KEY)['gorilla']
        self.assertIn('state', registered)
        self.assertIn('policy', registered)
        self.assertEqual(registered['policy']['name'], 'gorilla')
        self.assertEqual(registered['policy']['session_id'], 'test-session')
        self.assertEqual(registered['policy']['subject_details']['namespace'], 'model')
        self.assertIn('created_at', registered['policy'])
        ProxyPolicy.model_validate(registered['policy'])

    def test_query_set_proxy_rejects_wrong_state_shape_by_constructor_contract(self):
        with self.assertRaises(TypeError):
            GlueQuerySetProxy(name='bad', namespace='querySet', access=GlueAccess.VIEW)
