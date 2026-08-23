from types import SimpleNamespace

from django.http import HttpRequest
from django.test import SimpleTestCase

from django_glue.glue.attributes.callable import CallableAttribute


def context(**kwargs):
    return SimpleNamespace(request=HttpRequest(), target_attribute_call_kwargs=kwargs)


def attribute():
    instance = CallableAttribute.__new__(CallableAttribute)
    instance.name = 'process'

    return instance


class CallableParameterResolutionTestCase(SimpleTestCase):
    def test_variadic_keyword_parameter_is_not_required(self):
        def process(self, request: HttpRequest, step: int = 1, **kwargs):
            return step

        resolved = attribute()._resolve_call_parameters(process, context(step=2, extra='x'))

        self.assertEqual(resolved['step'], 2)
        self.assertEqual(resolved['extra'], 'x')
        self.assertIsInstance(resolved['request'], HttpRequest)
        self.assertNotIn('kwargs', resolved)

    def test_variadic_positional_parameter_is_not_required(self):
        def shout(self, volume: int, *args):
            return volume

        resolved = attribute()._resolve_call_parameters(shout, context(volume=3))

        self.assertEqual(resolved, {'volume': 3})

    def test_missing_required_parameter_still_raises(self):
        def shout(self, volume: int, **kwargs):
            return volume

        with self.assertRaises(ValueError):
            attribute()._resolve_call_parameters(shout, context())
