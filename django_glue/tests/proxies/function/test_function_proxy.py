"""
Tests for GlueFunctionProxy.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_project.settings')
django.setup()

from django.test import TestCase

from django_glue.access.access import GlueAccess
from django_glue.proxies import GlueFunctionProxy
from django_glue.resolver.action.schemas import ActionPayloadSchema
from django_glue.exceptions import GlueAccessError


def add_numbers(a, b):
    return a + b


def greet(name, greeting='Hello'):
    return f'{greeting}, {name}!'


def multiply_by_two(x):
    return x * 2


class GlueFunctionProxyInitTestCase(TestCase):
    """Tests for GlueFunctionProxy initialization."""

    def test_stores_function_path(self):
        proxy = GlueFunctionProxy(
            target='django_glue.tests.proxies.function.test_function_proxy.add_numbers',
            unique_name='add',
            access=GlueAccess.VIEW,
        )

        self.assertEqual(proxy.function_path, 'django_glue.tests.proxies.function.test_function_proxy.add_numbers')
        self.assertEqual(proxy.unique_name, 'add')

    def test_resolves_function_from_path(self):
        proxy = GlueFunctionProxy(
            target='django_glue.tests.proxies.function.test_function_proxy.add_numbers',
            unique_name='add',
            access=GlueAccess.VIEW,
        )

        self.assertEqual(proxy.function(3, 4), 7)

    def test_stores_params(self):
        proxy = GlueFunctionProxy(
            target='django_glue.tests.proxies.function.test_function_proxy.add_numbers',
            unique_name='add',
            access=GlueAccess.VIEW,
        )

        self.assertEqual(len(proxy._params), 2)
        self.assertEqual(proxy._params[0]['name'], 'a')
        self.assertEqual(proxy._params[1]['name'], 'b')

    def test_params_with_default_values(self):
        proxy = GlueFunctionProxy(
            target='django_glue.tests.proxies.function.test_function_proxy.greet',
            unique_name='greet',
            access=GlueAccess.VIEW,
        )

        self.assertEqual(len(proxy._params), 2)
        self.assertEqual(proxy._params[0]['name'], 'name')
        self.assertEqual(proxy._params[1]['name'], 'greeting')

    def test_raises_for_invalid_path(self):
        with self.assertRaises(ModuleNotFoundError):
            GlueFunctionProxy(
                target='not.a.valid.path',
                unique_name='bad',
                access=GlueAccess.VIEW,
            )


class GlueFunctionProxyContextDataTestCase(TestCase):
    """Tests for GlueFunctionProxy.to_context_data()."""

    def test_to_context_data_includes_subject_type_function(self):
        proxy = GlueFunctionProxy(
            target='django_glue.tests.proxies.function.test_function_proxy.add_numbers',
            unique_name='add',
            access=GlueAccess.VIEW,
        )

        context_data = proxy.to_context_data()

        self.assertEqual(context_data['subject_type'], 'Function')

    def test_to_context_data_includes_function_path(self):
        proxy = GlueFunctionProxy(
            target='django_glue.tests.proxies.function.test_function_proxy.add_numbers',
            unique_name='add',
            access=GlueAccess.VIEW,
        )

        context_data = proxy.to_context_data()

        self.assertEqual(context_data['function_path'], 'django_glue.tests.proxies.function.test_function_proxy.add_numbers')

    def test_to_context_data_includes_params(self):
        proxy = GlueFunctionProxy(
            target='django_glue.tests.proxies.function.test_function_proxy.greet',
            unique_name='greet',
            access=GlueAccess.VIEW,
        )

        context_data = proxy.to_context_data()

        self.assertIn('params', context_data)
        self.assertEqual(len(context_data['params']), 2)
        self.assertEqual(context_data['params'][0]['name'], 'name')
        self.assertEqual(context_data['params'][1]['name'], 'greeting')

    def test_to_context_data_includes_actions(self):
        proxy = GlueFunctionProxy(
            target='django_glue.tests.proxies.function.test_function_proxy.add_numbers',
            unique_name='add',
            access=GlueAccess.VIEW,
        )

        context_data = proxy.to_context_data()

        self.assertIn('actions', context_data)
        self.assertIn('execute', context_data['actions'])


class GlueFunctionProxyExecuteTestCase(TestCase):
    """Tests for GlueFunctionProxy.execute() action."""

    def test_execute_calls_function_with_args(self):
        proxy = GlueFunctionProxy(
            target='django_glue.tests.proxies.function.test_function_proxy.add_numbers',
            unique_name='add',
            access=GlueAccess.VIEW,
        )

        action_data = ActionPayloadSchema(
            context_data={},
            user_data={'a': 5, 'b': 10},
        )
        result = proxy.execute(action_data)

        self.assertEqual(result['result'], 15)

    def test_execute_with_string_return(self):
        proxy = GlueFunctionProxy(
            target='django_glue.tests.proxies.function.test_function_proxy.greet',
            unique_name='greet',
            access=GlueAccess.VIEW,
        )

        action_data = ActionPayloadSchema(
            context_data={},
            user_data={'name': 'World', 'greeting': 'Hi'},
        )
        result = proxy.execute(action_data)

        self.assertEqual(result['result'], 'Hi, World!')

    def test_execute_with_single_param(self):
        proxy = GlueFunctionProxy(
            target='django_glue.tests.proxies.function.test_function_proxy.multiply_by_two',
            unique_name='double',
            access=GlueAccess.VIEW,
        )

        action_data = ActionPayloadSchema(
            context_data={},
            user_data={'x': 21},
        )
        result = proxy.execute(action_data)

        self.assertEqual(result['result'], 42)

    def test_execute_with_partial_user_data(self):
        proxy = GlueFunctionProxy(
            target='django_glue.tests.proxies.function.test_function_proxy.greet',
            unique_name='greet',
            access=GlueAccess.VIEW,
        )

        action_data = ActionPayloadSchema(
            context_data={},
            user_data={'name': 'World'},
        )
        result = proxy.execute(action_data)

        self.assertEqual(result['result'], 'Hello, World!')


class GlueFunctionProxyFromActionRequestDataTestCase(TestCase):
    """Tests for GlueFunctionProxy.from_action_request_data()."""

    def test_from_action_request_data_reconstructs_proxy(self):
        proxy = GlueFunctionProxy.from_action_request_data(
            function_path='django_glue.tests.proxies.function.test_function_proxy.add_numbers',
            access=GlueAccess.VIEW,
            unique_name='add',
        )

        self.assertEqual(proxy.function_path, 'django_glue.tests.proxies.function.test_function_proxy.add_numbers')
        self.assertEqual(proxy.unique_name, 'add')
        self.assertEqual(proxy.access, GlueAccess.VIEW)
        self.assertEqual(proxy.function(2, 3), 5)

    def test_from_action_request_data_reconstructs_params(self):
        proxy = GlueFunctionProxy.from_action_request_data(
            function_path='django_glue.tests.proxies.function.test_function_proxy.greet',
            access=GlueAccess.CHANGE,
            unique_name='greet',
        )

        self.assertEqual(len(proxy._params), 2)
        self.assertEqual(proxy._params[0]['name'], 'name')


class GlueFunctionProxyProcessActionAccessTestCase(TestCase):
    """Tests for access control on GlueFunctionProxy actions."""

    def test_execute_with_view_access(self):
        proxy = GlueFunctionProxy(
            target='django_glue.tests.proxies.function.test_function_proxy.add_numbers',
            unique_name='add',
            access=GlueAccess.VIEW,
        )

        action_data = ActionPayloadSchema(
            context_data={},
            user_data={'a': 1, 'b': 2},
        )
        result = proxy.process_action('execute', action_data)

        self.assertEqual(result['result'], 3)

    def test_execute_with_higher_access(self):
        for access in [GlueAccess.CHANGE, GlueAccess.DELETE]:
            proxy = GlueFunctionProxy(
                target='django_glue.tests.proxies.function.test_function_proxy.add_numbers',
                unique_name='add',
                access=access,
            )

            action_data = ActionPayloadSchema(
                context_data={},
                user_data={'a': 1, 'b': 2},
            )
            result = proxy.process_action('execute', action_data)
            self.assertEqual(result['result'], 3)
