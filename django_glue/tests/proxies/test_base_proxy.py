"""
Tests for BaseGlueProxy process_action and core functionality.
"""
from django.test import TestCase

from django_glue.access.access import GlueAccess
from django_glue.proxies.proxy import BaseGlueProxy
from django_glue.proxies.model.proxy import GlueModelProxy
from django_glue.exceptions import GlueAccessError, GlueMissingActionError
from django_glue.resolver.action.schemas import ActionPayloadSchema
from test_project.gorilla.models import Gorilla


class BaseGlueProxyProcessActionTestCase(TestCase):
    """Tests for BaseGlueProxy.process_action()."""

    def setUp(self):
        self.gorilla = Gorilla.objects.create(
            name='Test Gorilla',
            description='Test',
            age=25,
            weight=350.0,
            height=1.8
        )

    def test_process_action_calls_decorated_method(self):
        """process_action should call the decorated method for valid actions."""
        proxy = GlueModelProxy(
            target=self.gorilla,
            unique_name='gorilla',
            access=GlueAccess.VIEW,
        )

        action_data = ActionPayloadSchema(context_data={})
        result = proxy.process_action('get', action_data)

        self.assertIsInstance(result, dict)
        self.assertEqual(result['name'], 'Test Gorilla')

    def test_process_action_raises_for_missing_action(self):
        """process_action should raise GlueMissingActionError for non-existent action."""
        proxy = GlueModelProxy(
            target=self.gorilla,
            unique_name='gorilla',
            access=GlueAccess.VIEW,
        )

        action_data = ActionPayloadSchema(context_data={})

        with self.assertRaises(GlueMissingActionError) as context:
            proxy.process_action('nonexistent_action', action_data)

        self.assertEqual(context.exception.action, 'nonexistent_action')

    def test_process_action_raises_for_insufficient_access(self):
        """process_action should raise GlueAccessError when access level is too low."""
        proxy = GlueModelProxy(
            target=self.gorilla,
            unique_name='gorilla',
            access=GlueAccess.VIEW,  # Not enough for save
        )

        action_data = ActionPayloadSchema(context_data={}, user_data={})

        with self.assertRaises(GlueAccessError) as context:
            proxy.process_action('save', action_data)

        self.assertEqual(context.exception.action, 'save')
        self.assertEqual(context.exception.required_access, 'CHANGE')
        self.assertEqual(context.exception.current_access, 'VIEW')

    def test_process_action_allows_higher_access(self):
        """process_action should allow higher access levels for actions."""
        proxy = GlueModelProxy(
            target=self.gorilla,
            unique_name='gorilla',
            access=GlueAccess.DELETE,  # Highest - should allow get (VIEW)
        )

        action_data = ActionPayloadSchema(context_data={})
        result = proxy.process_action('get', action_data)

        self.assertEqual(result['name'], 'Test Gorilla')


class BaseGlueProxyInitTestCase(TestCase):
    """Tests for BaseGlueProxy initialization."""

    def setUp(self):
        self.gorilla = Gorilla.objects.create(
            name='Test Gorilla',
            description='Test',
            age=25,
            weight=350.0,
            height=1.8
        )

    def test_accepts_glue_access_enum(self):
        """Proxy should accept GlueAccess enum for access parameter."""
        proxy = GlueModelProxy(
            target=self.gorilla,
            unique_name='gorilla',
            access=GlueAccess.CHANGE,
        )

        self.assertEqual(proxy.access, GlueAccess.CHANGE)

    def test_accepts_string_for_access(self):
        """Proxy should accept a string for access parameter."""
        proxy = GlueModelProxy(
            target=self.gorilla,
            unique_name='gorilla',
            access='view',
        )

        self.assertEqual(proxy.access, GlueAccess.VIEW)

    def test_stores_unique_name(self):
        """Proxy should store the unique_name."""
        proxy = GlueModelProxy(
            target=self.gorilla,
            unique_name='my_gorilla',
            access=GlueAccess.VIEW,
        )

        self.assertEqual(proxy.unique_name, 'my_gorilla')

    def test_raises_for_wrong_target_type(self):
        """Proxy should raise ValueError for wrong target type."""
        from django_glue.proxies.queryset.proxy import GlueQuerySetProxy

        with self.assertRaises(ValueError):
            GlueQuerySetProxy(
                target=self.gorilla,  # Model, not QuerySet
                unique_name='bad',
                access=GlueAccess.VIEW,
            )

    def test_default_access_is_view(self):
        """Proxy should default to VIEW access when not specified."""
        proxy = GlueModelProxy(
            target=self.gorilla,
            unique_name='gorilla',
        )

        self.assertEqual(proxy.access, GlueAccess.VIEW)
