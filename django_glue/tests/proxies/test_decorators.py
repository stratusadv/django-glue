from django.test import TestCase

from django_glue.access.access import GlueAccess
from django_glue.bound_attributes.decorators import bind_attribute
from django_glue.proxies.model.instance.proxy import GlueModelInstanceProxy


class BoundAttributeDecoratorTestCase(TestCase):
    """Tests for the @attribute decorator."""

    def test_sets_required_glue_access(self):
        """@attribute should set __required_glue_access__ on the wrapped function."""
        @bind_attribute(GlueAccess.VIEW)
        def my_attribute(self, event_data):
            return {'success': True}

        self.assertEqual(my_attribute.__required_glue_access__, GlueAccess.VIEW)

    def test_preserves_function_name(self):
        """@attribute should preserve the original function name via functools.wraps."""
        @bind_attribute(GlueAccess.CHANGE)
        def my_save_attribute(self, event_data):
            return {'success': True}

        self.assertEqual(my_save_attribute.__name__, 'my_save_attribute')

    def test_preserves_function_docstring(self):
        """@attribute should preserve the original function docstring."""
        @bind_attribute(GlueAccess.VIEW)
        def documented_attribute(self, event_data):
            """This is my bound attribute docstring."""
            return {'success': True}

        self.assertEqual(documented_attribute.__doc__, 'This is my bound attribute docstring.')


class BoundAttributeDecoratorProxyRegistrationTestCase(TestCase):
    """Tests for @attribute decorator integration with proxy binding discovery."""

    def test_attribute_is_discovered_in_proxy_bound_attributes(self):
        """Attributes decorated with @attribute should be discovered by discover_bound_attributes."""
        from test_project.gorilla.models import Gorilla  # noqa: PLC0415

        gorilla = Gorilla.objects.create(
            name='Test', description='Test', age=10, weight=200.0, height=1.5
        )
        state, _ = GlueModelInstanceProxy._build_state(gorilla)
        proxy = GlueModelInstanceProxy(name='test', namespace='model', access=GlueAccess.VIEW, state=state)

        bound_attributes = proxy.discover_bound_attributes()
        binding_names = [b.name for b in bound_attributes.values()]

        self.assertIn('get', binding_names)
        self.assertIn('save', binding_names)
        self.assertIn('delete', binding_names)
        self.assertIn('validate', binding_names)
        self.assertIn('foreign_key_choices', binding_names)

    def test_binding_stores_access_level(self):
        """Discovered bound_attributes should store their required access level."""
        from test_project.gorilla.models import Gorilla  # noqa: PLC0415

        gorilla = Gorilla.objects.create(
            name='Test', description='Test', age=10, weight=200.0, height=1.5
        )
        state, _ = GlueModelInstanceProxy._build_state(gorilla)
        proxy = GlueModelInstanceProxy(name='test', namespace='model', access=GlueAccess.VIEW, state=state)

        bound_attributes = proxy.discover_bound_attributes()

        get_binding = bound_attributes.get('GlueModelInstanceProxy.get')
        self.assertEqual(get_binding.required_access, GlueAccess.VIEW)

        save_binding = bound_attributes.get('GlueModelInstanceProxy.save')
        self.assertEqual(save_binding.required_access, GlueAccess.CHANGE)

        delete_binding = bound_attributes.get('GlueModelInstanceProxy.delete')
        self.assertEqual(delete_binding.required_access, GlueAccess.DELETE)

    def test_binding_stores_parameters(self):
        """Discovered bound_attributes should store their parameter annotations."""
        from test_project.gorilla.models import Gorilla  # noqa: PLC0415

        gorilla = Gorilla.objects.create(
            name='Test', description='Test', age=10, weight=200.0, height=1.5
        )
        state, _ = GlueModelInstanceProxy._build_state(gorilla)
        proxy = GlueModelInstanceProxy(name='test', namespace='model', access=GlueAccess.VIEW, state=state)

        bound_attributes = proxy.discover_bound_attributes()

        get_binding = bound_attributes.get('GlueModelInstanceProxy.get')
        self.assertEqual(get_binding.name, 'get')
