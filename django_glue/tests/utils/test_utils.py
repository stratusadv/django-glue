"""
Tests for Django Glue utility functions.
"""
import json

from django.test import TestCase, RequestFactory

from django_glue.utils import (
    get_request_body_data,
    get_class_from_path_string,
    serialize_queryset,
    deserialize_queryset,
)
from test_project.gorilla.models import Gorilla
from django_glue.proxies.proxy import BaseGlueProxy


class GetRequestBodyDataTestCase(TestCase):
    """Tests for get_request_body_data()."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_returns_full_body_dict(self):
        """Should return the full JSON body as a dict."""
        body = {'key': 'value', 'nested': {'a': 1}}
        request = self.factory.post(
            '/',
            data=json.dumps(body),
            content_type='application/json'
        )

        result = get_request_body_data(request)

        self.assertEqual(result, body)

    def test_returns_specific_key(self):
        """Should return the value for a specific key."""
        body = {'key': 'value', 'other': 'data'}
        request = self.factory.post(
            '/',
            data=json.dumps(body),
            content_type='application/json'
        )

        result = get_request_body_data(request, 'key')

        self.assertEqual(result, 'value')

    def test_returns_none_for_missing_key(self):
        """Should return None when the key doesn't exist."""
        body = {'key': 'value'}
        request = self.factory.post(
            '/',
            data=json.dumps(body),
            content_type='application/json'
        )

        result = get_request_body_data(request, 'missing')

        self.assertIsNone(result)


class GetClassFromPathStringTestCase(TestCase):
    """Tests for get_class_from_path_string()."""

    def test_returns_class_from_path(self):
        """Should return the class given a module path."""
        cls = get_class_from_path_string('test_project.gorilla.models.Gorilla')

        self.assertEqual(cls, Gorilla)

    def test_returns_function_from_path(self):
        """Should also work for functions."""
        func = get_class_from_path_string('django_glue.utils.get_request_body_data')

        self.assertEqual(func, get_request_body_data)

    def test_raises_for_invalid_module(self):
        """Should raise ModuleNotFoundError for invalid module path."""
        with self.assertRaises(ModuleNotFoundError):
            get_class_from_path_string('nonexistent.module.ClassName')

    def test_raises_for_invalid_class(self):
        """Should raise AttributeError for invalid class name."""
        with self.assertRaises(AttributeError):
            get_class_from_path_string('test_project.gorilla.models.NonExistent')


class SerializeQuerySetTestCase(TestCase):
    """Tests for serialize_queryset() and deserialize_queryset()."""

    def setUp(self):
        self.gorilla1 = Gorilla.objects.create(
            name='Gorilla 1',
            description='First',
            age=18,
            weight=200.0,
            height=1.8
        )
        self.gorilla2 = Gorilla.objects.create(
            name='Gorilla 2',
            description='Second',
            age=25,
            weight=250.0,
            height=2.0
        )

    def test_serialize_returns_dict(self):
        """serialize_queryset should return a safe dict (not pickle)."""
        qs = Gorilla.objects.all()
        encoded = serialize_queryset(qs)

        self.assertIsInstance(encoded, dict)
        self.assertIn('app_label', encoded)
        self.assertIn('model_name', encoded)
        self.assertIn('query_params', encoded)

    def test_deserialize_returns_queryset(self):
        """deserialize_queryset should return a QuerySet."""
        qs = Gorilla.objects.all()
        encoded = serialize_queryset(qs)
        restored = deserialize_queryset(encoded)

        from django.db.models import QuerySet
        self.assertIsInstance(restored, QuerySet)

    def test_roundtrip_preserves_results(self):
        """Serialize then deserialize should preserve queryset results."""
        qs = Gorilla.objects.all()
        encoded = serialize_queryset(qs)
        restored = deserialize_queryset(encoded)

        self.assertEqual(list(restored.values_list('pk', flat=True)), list(qs.values_list('pk', flat=True)))

    def test_roundtrip_preserves_ordering(self):
        """Serialize then deserialize should preserve queryset ordering."""
        qs = Gorilla.objects.order_by('-age')
        encoded = serialize_queryset(qs)
        restored = deserialize_queryset(encoded)

        self.assertEqual(list(restored.values_list('pk', flat=True)), list(qs.values_list('pk', flat=True)))
