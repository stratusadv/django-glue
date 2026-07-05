"""
Tests for Django Glue @action decorator.
"""
from django.test import TestCase

from django_glue.access.access import GlueAccess
from django_glue.proxies.decorators import action
from django_glue.proxies.proxy import BaseGlueProxy
from django_glue.proxies.model.instance.proxy import GlueModelInstanceProxy


class ActionDecoratorTestCase(TestCase):
    """Tests for the @action decorator."""

    def test_sets_required_glue_access(self):
        """@action should set _required_glue_access on the wrapped function."""
        @action(GlueAccess.VIEW)
        def my_action(self, action_data):
            return {'success': True}

        self.assertEqual(my_action._required_glue_access, GlueAccess.VIEW)

    def test_preserves_function_name(self):
        """@action should preserve the original function name via functools.wraps."""
        @action(GlueAccess.CHANGE)
        def my_save_action(self, action_data):
            return {'success': True}

        self.assertEqual(my_save_action.__name__, 'my_save_action')

    def test_preserves_function_docstring(self):
        """@action should preserve the original function docstring."""
        @action(GlueAccess.VIEW)
        def documented_action(self, action_data):
            """This is my action docstring."""
            return {'success': True}

        self.assertEqual(documented_action.__doc__, 'This is my action docstring.')

class ActionDecoratorProxyRegistrationTestCase(TestCase):
    """Tests for @action decorator integration with proxy class registration."""

    def test_action_is_registered_in_proxy_actions(self):
        """Actions decorated with @action should be registered in proxy._actions."""
        # GlueModelProxy already has get, save, delete, validate, foreign_key_choices
        actions = GlueModelInstanceProxy._actions['GlueModelProxy']

        self.assertIn('get', actions)
        self.assertIn('save', actions)
        self.assertIn('delete', actions)
        self.assertIn('validate', actions)
        self.assertIn('foreign_key_choices', actions)

    def test_action_registration_stores_access_level(self):
        """Registered actions should store their required access level."""
        actions = GlueModelInstanceProxy._actions['GlueModelProxy']

        # get requires VIEW
        _, _, access = actions['get']
        self.assertEqual(access, GlueAccess.VIEW)

        # save requires CHANGE
        _, _, access = actions['save']
        self.assertEqual(access, GlueAccess.CHANGE)

        # delete requires DELETE
        _, _, access = actions['delete']
        self.assertEqual(access, GlueAccess.DELETE)

    def test_action_registration_stores_parameters(self):
        """Registered actions should store their parameter annotations."""
        actions = GlueModelInstanceProxy._actions['GlueModelProxy']

        # get should have action_data parameter
        _, params, _ = actions['get']
        self.assertIn('action_data', params)

    def test_raises_type_error_for_non_proxy_class(self):
        """@action should raise TypeError when called on a non-BaseGlueProxy instance."""
        @action(GlueAccess.VIEW)
        def my_action(self, action_data):
            return {'success': True}

        class NotAProxy:
            pass

        with self.assertRaises(TypeError) as context:
            my_action(NotAProxy(), None)

        self.assertIn('must inherit from BaseGlueProxy', str(context.exception))
