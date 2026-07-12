import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_project.settings')
django.setup()

from django.test import TestCase

from django_glue.access.access import GlueAccess
from django_glue.tests.proxies.form.helpers import make_form_proxy
from test_project.gorilla.forms import GorillaForm
from test_project.gorilla.models import Gorilla, Skill
from test_project.test_forms import ContactForm, TestModelForm


class GlueFormProxyBoundAttributesTestCase(TestCase):
    def test_discovers_form_bound_attributes(self):
        proxy = make_form_proxy(ContactForm())

        bound_attributes = {
            name.split('.')[-1]: binding
            for name, binding in proxy.discover_bound_attributes().items()
        }

        self.assertIn('load', bound_attributes)
        self.assertIn('validate', bound_attributes)
        self.assertIn('save', bound_attributes)
        self.assertIn('foreign_key_choices', bound_attributes)

    def test_validate_returns_true_for_valid_bound_form(self):
        proxy = make_form_proxy(ContactForm(data={
            'name': 'John Doe',
            'email': 'john@example.com',
            'message': 'Hello world',
            'priority': 'medium',
        }))

        self.assertEqual(proxy.validate(request=None), {'valid': True})

    def test_validate_returns_false_and_populates_errors_for_invalid_bound_form(self):
        proxy = make_form_proxy(ContactForm(data={
            'name': '',
            'email': 'not-an-email',
            'message': 'Hello',
            'priority': 'medium',
        }))

        self.assertEqual(proxy.validate(request=None), {'valid': False})
        self.assertIn('name', proxy.state.errors)
        self.assertIn('email', proxy.state.errors)

    def test_validate_is_registered_with_change_access(self):
        proxy = make_form_proxy(ContactForm())
        bound_attributes = proxy.discover_bound_attributes()

        self.assertEqual(
            bound_attributes['GlueFormProxy.validate'].required_access,
            GlueAccess.CHANGE,
        )

    def test_save_persists_valid_model_form(self):
        gorilla = Gorilla.objects.create(
            name='Original',
            description='Before',
            age=20,
            weight=200.0,
            height=1.8,
        )
        form = TestModelForm(
            data={
                'name': 'Updated',
                'description': 'After',
                'age': 21,
                'weight': 210.0,
                'height': 1.9,
            },
            instance=gorilla,
        )
        proxy = make_form_proxy(form, access=GlueAccess.CHANGE)

        result = proxy.save(request=None)

        gorilla.refresh_from_db()
        self.assertIsNone(result)
        self.assertEqual(gorilla.name, 'Updated')
        self.assertEqual(gorilla.description, 'After')

    def test_save_does_not_persist_invalid_model_form(self):
        gorilla = Gorilla.objects.create(
            name='Original',
            description='Before',
            age=20,
            weight=200.0,
            height=1.8,
        )
        form = TestModelForm(
            data={
                'name': '',
                'description': 'After',
                'age': 21,
                'weight': 210.0,
                'height': 1.9,
            },
            instance=gorilla,
        )
        proxy = make_form_proxy(form, access=GlueAccess.CHANGE)

        proxy.save(request=None)

        gorilla.refresh_from_db()
        self.assertEqual(gorilla.name, 'Original')
        self.assertIn('name', proxy.state.errors)

    def test_save_is_registered_with_change_access(self):
        proxy = make_form_proxy(ContactForm())
        bound_attributes = proxy.discover_bound_attributes()

        self.assertEqual(
            bound_attributes['GlueFormProxy.save'].required_access,
            GlueAccess.CHANGE,
        )

    def test_foreign_key_choices_returns_empty_for_missing_field_name(self):
        proxy = make_form_proxy(ContactForm())

        self.assertEqual(proxy.foreign_key_choices(request=None), [])

    def test_foreign_key_choices_returns_model_choice_values(self):
        skill = Skill.objects.create(name='Climb', description='Trees')

        form = GorillaForm()
        proxy = make_form_proxy(form)

        self.assertEqual(
            proxy.foreign_key_choices(request=None, field_name='skills'),
            [{'pk': skill.pk, '__str__': 'Climb'}],
        )

    def test_load_returns_none(self):
        proxy = make_form_proxy(ContactForm())

        self.assertIsNone(proxy.load(request=None))
