import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_project.settings')
django.setup()

from django.test import RequestFactory, TestCase

from django_glue.access.access import GlueAccess
from django_glue.constants import DJANGO_GLUE_PROXIES_REQUEST_ATTR_KEY
from django_glue.proxies.function.proxy import GlueFunctionProxy
from django_glue.proxies.function.state import GlueFunctionProxyState
from django_glue.tests.conftest import MockSession


FUNCTION_PATH = 'django_glue.tests.proxies.function.test_function_proxy.add_numbers'
GREET_PATH = 'django_glue.tests.proxies.function.test_function_proxy.greet'
DOUBLE_PATH = 'django_glue.tests.proxies.function.test_function_proxy.multiply_by_two'


def add_numbers(a, b):
    return a + b


def greet(name, greeting='Hello'):
    return f'{greeting}, {name}!'


def multiply_by_two(x):
    return x * 2


def make_function_proxy(function_path=FUNCTION_PATH, name='add', access=GlueAccess.VIEW):
    return GlueFunctionProxy(
        name=name,
        namespace='function',
        access=access,
        state=GlueFunctionProxyState(function_path=function_path),
    )


class GlueFunctionProxyStateTestCase(TestCase):
    def test_stores_function_path_in_state(self):
        proxy = make_function_proxy()

        self.assertEqual(proxy.state.function_path, FUNCTION_PATH)
        self.assertEqual(proxy.name, 'add')
        self.assertEqual(proxy.access, GlueAccess.VIEW)

    def test_serializes_runtime_state(self):
        state = GlueFunctionProxyState(function_path=FUNCTION_PATH, previous_kwargs={'a': 1})

        self.assertEqual(
            state.serialize(),
            {'namespace': 'function', 'previous_kwargs': {'a': 1}},
        )


class GlueFunctionProxyPolicyTestCase(TestCase):
    def test_custom_policy_details_include_function_path(self):
        proxy = make_function_proxy()

        self.assertEqual(proxy._custom_policy_details['function_path'], FUNCTION_PATH)

    def test_register_policy_serializes_params(self):
        request = RequestFactory().get('/')
        request.session = MockSession()

        GlueFunctionProxy.register_policy(
            request=request,
            target=GREET_PATH,
            name='greet',
            access=GlueAccess.VIEW,
        )

        registered = getattr(request, DJANGO_GLUE_PROXIES_REQUEST_ATTR_KEY)['greet']
        subject_details = registered['policy']['subject_details']

        self.assertEqual(subject_details['namespace'], 'function')
        self.assertEqual(subject_details['function_path'], GREET_PATH)
        self.assertEqual(
            [param['name'] for param in subject_details['params']],
            ['name', 'greeting'],
        )

    def test_register_policy_raises_for_invalid_path(self):
        request = RequestFactory().get('/')
        request.session = MockSession()

        with self.assertRaises(ModuleNotFoundError):
            GlueFunctionProxy.register_policy(
                request=request,
                target='not.a.valid.path',
                name='bad',
            )


class GlueFunctionProxyBoundAttributesTestCase(TestCase):
    def test_discovers_execute_bound_attribute(self):
        proxy = make_function_proxy()

        bound_attributes = proxy.discover_bound_attributes()

        self.assertIn('GlueFunctionProxy.execute', bound_attributes)
        self.assertEqual(
            bound_attributes['GlueFunctionProxy.execute'].required_access,
            GlueAccess.VIEW,
        )

    def test_execute_calls_function_with_kwargs(self):
        proxy = make_function_proxy()

        result = proxy.execute(request=None, a=5, b=10)

        self.assertEqual(result, {'result': 15})

    def test_execute_uses_function_default_values(self):
        proxy = make_function_proxy(function_path=GREET_PATH, name='greet')

        result = proxy.execute(request=None, name='World')

        self.assertEqual(result, {'result': 'Hello, World!'})

    def test_execute_with_string_return(self):
        proxy = make_function_proxy(function_path=GREET_PATH, name='greet')

        result = proxy.execute(request=None, name='World', greeting='Hi')

        self.assertEqual(result, {'result': 'Hi, World!'})

    def test_execute_with_single_param(self):
        proxy = make_function_proxy(function_path=DOUBLE_PATH, name='double')

        result = proxy.execute(request=None, x=21)

        self.assertEqual(result, {'result': 42})
