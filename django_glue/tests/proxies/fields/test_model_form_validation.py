import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_project.settings')
django.setup()

from django.test import TestCase

from django_glue.access.access import GlueAccess
from django_glue.tests.proxies.model.helpers import make_model_proxy
from test_project.gorilla.models import Gorilla


class ModelProxyFormValidationTestCase(TestCase):
    def setUp(self):
        self.gorilla = Gorilla.objects.create(
            name='Test Gorilla',
            description='Test description',
            age=18,
            weight=200.0,
            height=1.8,
        )

    def bind_proxy_form(self, proxy, data):
        proxy.state.form = proxy.state.form.__class__(data=data, instance=self.gorilla)

    def test_validates_all_included_fields(self):
        proxy = make_model_proxy(self.gorilla, access=GlueAccess.CHANGE)
        self.bind_proxy_form(proxy, {
            'name': 'Updated Name',
            'description': 'Test description',
            'age': 5,
            'weight': 200.0,
            'height': 1.8,
            'rank_points': 0,
        })

        self.assertEqual(proxy.validate(request=None), {'valid': True})
        self.assertEqual(proxy.state.form.cleaned_data['name'], 'Updated Name')
        self.assertEqual(proxy.state.form.cleaned_data['age'], 5)

    def test_filters_out_non_included_fields(self):
        proxy = make_model_proxy(self.gorilla, access=GlueAccess.CHANGE, fields=['name', 'age'])
        self.bind_proxy_form(proxy, {
            'name': 'Updated',
            'age': 10,
            'description': 'Ignored',
            'weight': 999,
        })

        self.assertEqual(proxy.validate(request=None), {'valid': True})
        self.assertIn('name', proxy.state.form.cleaned_data)
        self.assertIn('age', proxy.state.form.cleaned_data)
        self.assertNotIn('description', proxy.state.form.cleaned_data)
        self.assertNotIn('weight', proxy.state.form.cleaned_data)

    def test_invalid_payload_populates_errors(self):
        proxy = make_model_proxy(self.gorilla, access=GlueAccess.CHANGE)
        self.bind_proxy_form(proxy, {'name': '', 'age': 1})

        self.assertEqual(proxy.validate(request=None), {'valid': False})
        self.assertIn('name', proxy.state.errors)

    def test_form_validation_coerces_data_types(self):
        proxy = make_model_proxy(self.gorilla, access=GlueAccess.CHANGE)
        self.bind_proxy_form(proxy, {
            'name': 'Test Gorilla',
            'description': '',
            'age': '42',
            'weight': 200.0,
            'height': 1.8,
            'rank_points': 0,
        })

        self.assertEqual(proxy.validate(request=None), {'valid': True})
        self.assertEqual(proxy.state.form.cleaned_data['age'], 42)
        self.assertIsInstance(proxy.state.form.cleaned_data['age'], int)

    def test_validates_max_length(self):
        proxy = make_model_proxy(self.gorilla, access=GlueAccess.CHANGE)
        self.bind_proxy_form(proxy, {
            'name': 'x' * 260,
            'age': 1,
            'weight': 200.0,
            'height': 1.8,
            'rank_points': 0,
        })

        self.assertEqual(proxy.validate(request=None), {'valid': False})
        self.assertIn('name', proxy.state.errors)

    def test_validates_min_value(self):
        proxy = make_model_proxy(self.gorilla, access=GlueAccess.CHANGE)
        self.bind_proxy_form(proxy, {
            'name': 'Test',
            'age': 0,
            'weight': 200.0,
            'height': 1.8,
            'rank_points': 0,
        })

        self.assertEqual(proxy.validate(request=None), {'valid': False})
        self.assertIn('age', proxy.state.errors)

    def test_validates_max_value(self):
        proxy = make_model_proxy(self.gorilla, access=GlueAccess.CHANGE)
        self.bind_proxy_form(proxy, {
            'name': 'Test',
            'age': 61,
            'weight': 200.0,
            'height': 1.8,
            'rank_points': 0,
        })

        self.assertEqual(proxy.validate(request=None), {'valid': False})
        self.assertIn('age', proxy.state.errors)

    def test_allows_blank_field(self):
        proxy = make_model_proxy(self.gorilla, access=GlueAccess.CHANGE)
        self.bind_proxy_form(proxy, {
            'name': 'Test',
            'description': '',
            'age': 1,
            'weight': 200.0,
            'height': 1.8,
            'rank_points': 0,
        })

        self.assertEqual(proxy.validate(request=None), {'valid': True})
        self.assertEqual(proxy.state.form.cleaned_data['description'], '')

    def test_save_persists_valid_bound_form(self):
        proxy = make_model_proxy(self.gorilla, access=GlueAccess.CHANGE)
        self.bind_proxy_form(proxy, {
            'name': 'Updated Name',
            'description': 'Test description',
            'age': 1,
            'weight': 200.0,
            'height': 1.8,
            'rank_points': 0,
        })

        proxy.save(request=None)

        self.gorilla.refresh_from_db()
        self.assertEqual(self.gorilla.name, 'Updated Name')

    def test_save_does_not_persist_invalid_bound_form(self):
        proxy = make_model_proxy(self.gorilla, access=GlueAccess.CHANGE)
        self.bind_proxy_form(proxy, {'name': '', 'age': 1, 'weight': 200.0, 'height': 1.8})

        proxy.save(request=None)

        self.gorilla.refresh_from_db()
        self.assertEqual(self.gorilla.name, 'Test Gorilla')
        self.assertIn('name', proxy.state.errors)
