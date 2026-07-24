"""
Tests for Django Glue utility functions.
"""
import json

from django.test import TestCase, RequestFactory

from django_glue.utils import (
    get_request_body_data,
    get_attr_from_path_string,
)
from test_project.gorilla.models import Gorilla


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
        cls = get_attr_from_path_string('test_project.gorilla.models.Gorilla')

        self.assertEqual(cls, Gorilla)

    def test_returns_function_from_path(self):
        """Should also work for functions."""
        func = get_attr_from_path_string('django_glue.utils.get_request_body_data')

        self.assertEqual(func, get_request_body_data)

    def test_raises_for_invalid_module(self):
        """Should raise ModuleNotFoundError for invalid module path."""
        with self.assertRaises(ModuleNotFoundError):
            get_attr_from_path_string('nonexistent.module.ClassName')

    def test_raises_for_invalid_class(self):
        """Should raise AttributeError for invalid class name."""
        with self.assertRaises(AttributeError):
            get_attr_from_path_string('test_project.gorilla.models.NonExistent')

