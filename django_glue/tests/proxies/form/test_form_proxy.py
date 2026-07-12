"""
Tests for GlueFormProxy basic functionality.
"""

import os
import django
from types import SimpleNamespace

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_project.settings')
django.setup()

from django.test import TestCase
from django.forms import modelform_factory

from django_glue.access.access import GlueAccess
from django_glue.proxies.form.state import GlueFormProxyState
from django_glue.tests.proxies.form.helpers import make_form_proxy
from test_project.fight.choices import (
    FightStatusChoices,
    LocationChoices,
    TerrainTypeChoices,
    WeatherConditionChoices,
)
from test_project.fight.forms import FightForm
from test_project.test_forms import ContactForm, TestModelForm
from test_project.gorilla.forms import GorillaForm
from test_project.gorilla.models import Gorilla, Skill


class GlueFormProxyInitTestCase(TestCase):
    """Tests for GlueFormProxy initialization."""

    def test_accepts_form_instance(self):
        """Should accept a Django Form instance."""
        form = ContactForm()
        proxy = make_form_proxy(form, access=GlueAccess.CHANGE)
        self.assertEqual(proxy.name, 'contact_form')
        self.assertEqual(proxy.access, GlueAccess.CHANGE)
        self.assertIs(proxy.state.form, form)

    def test_accepts_model_form_instance(self):
        """Should accept a Django ModelForm instance."""
        form = TestModelForm()
        proxy = make_form_proxy(form, name='task_form', access=GlueAccess.CHANGE)
        self.assertEqual(proxy.name, 'task_form')
        self.assertIs(proxy.state.form, form)

    def test_stores_form_class_info(self):
        """Should store form class name and module."""
        form = ContactForm()
        proxy = make_form_proxy(form, access=GlueAccess.CHANGE)
        self.assertEqual(
            proxy._custom_policy_details['form_class_path'],
            'test_project.test_forms.ContactForm',
        )


class GlueFormProxyFieldDefinitionsTestCase(TestCase):
    """Tests for _form_field_definitions property."""

    def test_extracts_field_types(self):
        """Should extract field type names."""
        form = ContactForm()
        proxy = make_form_proxy(form)
        fields = proxy._field_metadata

        self.assertEqual(fields['name']['type'], 'CharField')
        self.assertEqual(fields['email']['type'], 'EmailField')
        self.assertEqual(fields['message']['type'], 'CharField')
        self.assertEqual(fields['priority']['type'], 'ChoiceField')

    def test_extracts_required_flag(self):
        """Should extract required flag for each field."""
        form = ContactForm()
        proxy = make_form_proxy(form)
        fields = proxy._field_metadata

        self.assertTrue(fields['name']['required'])
        self.assertTrue(fields['email']['required'])

    def test_extracts_labels(self):
        """Should extract field labels, falling back to field name if None."""
        form = ContactForm()
        proxy = make_form_proxy(form)
        fields = proxy._field_metadata

        # Default labels are field names when not explicitly set
        self.assertEqual(fields['name']['label'], 'name')
        self.assertEqual(fields['email']['label'], 'email')

    def test_extracts_widget_type(self):
        """Should extract widget class name."""
        form = ContactForm()
        proxy = make_form_proxy(form)
        fields = proxy._field_metadata

        self.assertEqual(fields['message']['widget'], 'Textarea')

    def test_extracts_choices(self):
        """Should extract choices for choice fields."""
        form = ContactForm()
        proxy = make_form_proxy(form)
        fields = proxy._field_metadata

        self.assertIn('choices', fields['priority'])
        self.assertEqual(len(fields['priority']['choices']), 3)

    def test_extracts_model_choice_cache_metadata(self):
        """Should include stable metadata for queryset-backed choice fields."""
        form_class = modelform_factory(Gorilla, fields=['name', 'skills'])
        form = form_class()
        proxy = make_form_proxy(form)
        field = proxy._field_metadata['skills']

        self.assertEqual(field['choices'], [])
        self.assertEqual(field['pk_field'], Skill._meta.pk.name)
        self.assertEqual(field['choice_model_path'], 'test_project.gorilla.models.Skill')
        self.assertEqual(
            field['choices_cache_key'],
            f'{form.__class__.__module__}.{form.__class__.__name__}.skills.gorilla.skill',
        )

    def test_extracts_max_length(self):
        """Should extract max_length if present."""
        form = ContactForm()
        proxy = make_form_proxy(form)
        fields = proxy._field_metadata

        self.assertEqual(fields['name']['max_length'], 100)


class GlueFormProxyInitialValuesTestCase(TestCase):
    """Tests for serialized form state."""

    def test_returns_empty_values_for_new_form(self):
        """Should serialize empty instance data for fields without initial values."""
        form = ContactForm()
        proxy = make_form_proxy(form)
        state = proxy.state.serialize()

        self.assertEqual(state['instance_data'], {})

    def test_returns_initial_values_from_form(self):
        """Should return initial values passed to form."""
        form = ContactForm(initial={'name': 'John', 'email': 'john@example.com'})
        proxy = make_form_proxy(form)
        values = proxy.state.serialize()['instance_data']

        self.assertEqual(values['name'], 'John')
        self.assertEqual(values['email'], 'john@example.com')

    def test_returns_instance_values_for_model_form(self):
        """Should return instance values for ModelForm."""
        gorilla = Gorilla.objects.create(
            name='Test Gorilla', description='Test description', age=25, weight=350.0, height=1.8
        )
        form = TestModelForm(instance=gorilla)
        proxy = make_form_proxy(form, name='task_form')
        values = proxy.state.serialize()['instance_data']

        self.assertEqual(values['name'], 'Test Gorilla')
        self.assertEqual(values['description'], 'Test description')
        self.assertEqual(values['age'], 25)
        self.assertEqual(values['weight'], 350.0)


class GlueFormProxyContextDataTestCase(TestCase):
    """Tests for context data serialization."""

    def test_includes_form_class_path(self):
        """Should include full form class path in context data."""
        form = ContactForm()
        proxy = make_form_proxy(form)
        context_data = proxy._custom_policy_details

        self.assertEqual(context_data['form_class_path'], 'test_project.test_forms.ContactForm')

    def test_includes_fields(self):
        """Should include field definitions in context data."""
        form = ContactForm()
        proxy = make_form_proxy(form)
        context_data = proxy._custom_policy_details

        self.assertIn('included_fields', context_data)
        self.assertIn('name', context_data['included_fields'])

    def test_includes_initial(self):
        """Should include initial values in context data."""
        form = ContactForm(initial={'name': 'John'})
        proxy = make_form_proxy(form)
        state_data = proxy.state.serialize()

        self.assertIn('instance_data', state_data)
        self.assertEqual(state_data['instance_data']['name'], 'John')

    def test_includes_bound_attributes(self):
        """Should include available bound attributes in context data."""
        form = ContactForm()
        proxy = make_form_proxy(form)
        bound_attributes = {
            name.split('.')[-1]: binding
            for name, binding in proxy.discover_bound_attributes().items()
        }

        self.assertIn('load', bound_attributes)
        self.assertIn('validate', bound_attributes)
        self.assertIn('save', bound_attributes)

    def test_foreign_key_choices_returns_empty_for_missing_field_definition(self):
        """foreign_key_choices should return empty list when field_definition is missing."""
        form = ContactForm()
        proxy = make_form_proxy(form)
        result = proxy.foreign_key_choices(request=None, field_name=None)
        self.assertEqual(result, [])


class GlueFormProxyStateNormalizationTestCase(TestCase):
    """Tests for rebuilding Django forms from JSON proxy state."""

    def _event_for_form(self, form_class, instance_data, target_pk=None):
        return SimpleNamespace(
            policy=SimpleNamespace(
                subject_details=SimpleNamespace(
                    form_class_path=f'{form_class.__module__}.{form_class.__name__}',
                    target_pk=target_pk,
                ),
            ),
            request=SimpleNamespace(FILES={}),
            proxy_state={'instance_data': instance_data},
        )

    def test_deserialize_normalizes_model_choice_object_to_primary_key(self):
        red_corner = Gorilla.objects.create(name='Red', age=20, weight=300, height=1.7)
        blue_corner = Gorilla.objects.create(name='Blue', age=21, weight=310, height=1.8)

        form = GlueFormProxyState._build_form_instance_from_event(self._event_for_form(
            FightForm,
            {
                'name': 'Test Fight',
                'description': 'Test description',
                'red_corner': {'id': red_corner.pk, 'name': red_corner.name},
                'blue_corner': blue_corner.pk,
                'status': FightStatusChoices.SCHEDULED,
                'location': LocationChoices.DINOSAUR_ISLAND,
                'weather_conditions': WeatherConditionChoices.PERFECT_BLUE_SKY,
                'spectator_count': 10,
                'terrain_type': TerrainTypeChoices.STEEL_DEATH_CAGE,
            },
        ))

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['red_corner'], red_corner)
        self.assertEqual(form.cleaned_data['blue_corner'], blue_corner)

    def test_deserialize_normalizes_model_multiple_choice_objects_to_primary_keys(self):
        skill = Skill.objects.create(name='Grappling')
        gorilla = Gorilla.objects.create(name='Fighter', age=20, weight=300, height=1.7)

        form = GlueFormProxyState._build_form_instance_from_event(self._event_for_form(
            GorillaForm,
            {
                'name': gorilla.name,
                'description': gorilla.description,
                'age': gorilla.age,
                'weight': gorilla.weight,
                'height': gorilla.height,
                'rank_points': 0,
                'skills': [{'id': skill.pk, 'name': skill.name}],
            },
            target_pk=gorilla.pk,
        ))

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(list(form.cleaned_data['skills']), [skill])
