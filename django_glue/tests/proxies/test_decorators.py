from django.test import TestCase
import inspect

from django_glue.access.access import GlueAccess
from django_glue.bound_attributes.attribute import discover_bound_attributes_on_target
from django_glue.bound_attributes.decorators import Attribute
from django_glue.proxies.model.instance.proxy import GlueModelInstanceProxy


class BoundAttributeDecoratorTestCase(TestCase):
    """Tests for the @attribute decorator."""

    def test_sets_required_glue_access(self):
        """@attribute should set __required_glue_access__ on the wrapped function."""
        @Attribute(access=GlueAccess.VIEW)
        def my_attribute(self, event_data):
            return {'success': True}

        self.assertEqual(my_attribute.__required_glue_access__, GlueAccess.VIEW)

    def test_preserves_function_name(self):
        """@attribute should preserve the original function name via functools.wraps."""
        @Attribute(access=GlueAccess.CHANGE)
        def my_save_attribute(self, event_data):
            return {'success': True}

        self.assertEqual(my_save_attribute.__name__, 'my_save_attribute')

    def test_preserves_function_docstring(self):
        """@attribute should preserve the original function docstring."""
        @Attribute(access=GlueAccess.VIEW)
        def documented_attribute(self, event_data):
            """This is my bound attribute docstring."""
            return {'success': True}

        self.assertEqual(documented_attribute.__doc__, 'This is my bound attribute docstring.')

    def test_descriptor_stores_non_callable_attribute(self):
        class Example:
            status = Attribute('ready', access=GlueAccess.VIEW)

        example = Example()

        self.assertEqual(example.status, 'ready')
        example.status = 'busy'
        self.assertEqual(example.status, 'busy')
        self.assertEqual(Example.status.__required_glue_access__, GlueAccess.VIEW)
        self.assertFalse(Example.status.is_callable)

    def test_decorates_computed_property(self):
        class Example:
            @Attribute(access=GlueAccess.VIEW)
            @property
            def status(self):
                return 'computed'

        example = Example()
        self.assertEqual(example.status, 'computed')
        static_status = inspect.getattr_static(Example, 'status')
        self.assertEqual(static_status.__required_glue_access__, GlueAccess.VIEW)
        self.assertFalse(static_status.is_callable)

    def test_wraps_descriptor_attribute(self):
        class StatusDescriptor:
            def __get__(self, instance, owner):
                if instance is None:
                    return self
                return 'descriptor'

        class Example:
            status = Attribute(StatusDescriptor(), access=GlueAccess.VIEW)

        example = Example()

        self.assertEqual(example.status, 'descriptor')
        self.assertIsInstance(Example.status, StatusDescriptor)
        static_status = inspect.getattr_static(Example, 'status')
        self.assertEqual(static_status.__required_glue_access__, GlueAccess.VIEW)
        self.assertFalse(static_status.is_callable)

    def test_discovers_non_callable_attributes(self):
        class Example:
            status = Attribute('ready', access=GlueAccess.VIEW)

            @Attribute(access=GlueAccess.CHANGE)
            @property
            def computed_status(self):
                return 'computed'

        bound_attributes = discover_bound_attributes_on_target(Example())

        self.assertEqual(bound_attributes['Example.status'].required_access, GlueAccess.VIEW)
        self.assertFalse(bound_attributes['Example.status'].is_callable)
        self.assertEqual(
            bound_attributes['Example.computed_status'].required_access,
            GlueAccess.CHANGE,
        )
        self.assertFalse(bound_attributes['Example.computed_status'].is_callable)

    def test_wrapped_descriptor_class_access_and_nested_discovery(self):
        class Service:
            @Attribute(access=GlueAccess.CHANGE)
            def save_model_obj(self):
                return 'saved'

        class ServicesDescriptor:
            def __get__(self, instance, owner):
                return Service()

        class Example:
            services = Attribute(ServicesDescriptor(), access=GlueAccess.VIEW)

        self.assertEqual(Example.services.save_model_obj(), 'saved')

        bound_attributes = discover_bound_attributes_on_target(Example())

        self.assertIn('Example.services.save_model_obj', bound_attributes)
        self.assertEqual(
            bound_attributes['Example.services.save_model_obj'].required_access,
            GlueAccess.CHANGE,
        )


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
