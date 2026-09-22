"""A callable's return annotation must never be able to break the call.

Only parameter hints matter when building call kwargs. The return annotation is
not consulted -- but resolving the whole signature at once made it fatal, which
broke exactly the shape the design asks for: a callable that returns a
configured Glue object and annotates it, with the Glue class imported under
TYPE_CHECKING.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

from django.http import HttpRequest
from django.test import SimpleTestCase

from django_glue.glue.attributes.callable import CallableAttribute

if TYPE_CHECKING:
    from django_glue.glue.objects.django.model.object import ModelGlue
    from django_glue.glue.objects.django.queryset import QuerySetGlue


def context(**kwargs):
    return SimpleNamespace(request=HttpRequest(), target_attribute_call_kwargs=kwargs)


def attribute():
    instance = CallableAttribute.__new__(CallableAttribute)
    instance.name = 'process'

    return instance


class ReturnAnnotationTestCase(SimpleTestCase):
    def test_a_type_checking_only_return_annotation_does_not_break_the_call(self):
        """ModelGlue is imported under TYPE_CHECKING, so it cannot be resolved."""
        def new_entry(self, request: HttpRequest) -> ModelGlue:
            return None

        resolved = attribute()._resolve_call_parameters(new_entry, context())

        self.assertIsInstance(resolved['request'], HttpRequest)

    def test_request_injection_still_works_alongside_one(self):
        def new_entry(self, request: HttpRequest, entry_id: int) -> QuerySetGlue:
            return None

        resolved = attribute()._resolve_call_parameters(new_entry, context(entry_id=7))

        self.assertIsInstance(resolved['request'], HttpRequest)
        self.assertEqual(resolved['entry_id'], 7)

    def test_a_quoted_forward_reference_parameter_still_resolves(self):
        """`request: 'HttpRequest'` is the string "'HttpRequest'" here, so it
        needs resolving twice."""
        def render(self, request: 'HttpRequest') -> ModelGlue:
            return None

        resolved = attribute()._resolve_call_parameters(render, context())

        self.assertIsInstance(resolved['request'], HttpRequest)

    def test_an_unresolvable_parameter_annotation_is_skipped_not_fatal(self):
        """It only means that parameter cannot be matched for injection."""
        def process(self, request: HttpRequest, thing: Nonexistent = None):  # noqa: F821
            return thing

        resolved = attribute()._resolve_call_parameters(process, context())

        self.assertIsInstance(resolved['request'], HttpRequest)
        self.assertNotIn('thing', resolved)

    def test_a_resolvable_return_annotation_is_not_passed_as_a_parameter(self):
        def save(self, request: HttpRequest) -> dict:
            return {}

        resolved = attribute()._resolve_call_parameters(save, context())

        self.assertNotIn('return', resolved)
