"""
Tests for GlueFormProxy basic functionality.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_project.base_settings')
django.setup()

from django.test import TestCase

from django_glue.access.access import GlueAccess
from django_glue.proxies.form.proxy import GlueFormProxy
from test_project.task.forms import TaskForm, ContactForm
from test_project.task.models import Task


class GlueFormProxyInitTestCase(TestCase):
    """Tests for GlueFormProxy initialization."""

    def test_accepts_form_instance(self):
        """Should accept a Django Form instance."""
        form = ContactForm()
        proxy = GlueFormProxy(
            target=form,
            unique_name='contact_form',
            access=GlueAccess.CHANGE,
        )
        self.assertEqual(proxy.unique_name, 'contact_form')
        self.assertEqual(proxy.access, GlueAccess.CHANGE)

    def test_accepts_model_form_instance(self):
        """Should accept a Django ModelForm instance."""
        form = TaskForm()
        proxy = GlueFormProxy(
            target=form,
            unique_name='task_form',
            access=GlueAccess.CHANGE,
        )
        self.assertEqual(proxy.unique_name, 'task_form')

    def test_stores_form_class_info(self):
        """Should store form class name and module."""
        form = ContactForm()
        proxy = GlueFormProxy(
            target=form,
            unique_name='contact_form',
            access=GlueAccess.CHANGE,
        )
        self.assertEqual(proxy.form_class_name, 'ContactForm')
        self.assertEqual(proxy.form_module, 'test_project.task.forms')


class GlueFormProxyFieldDefinitionsTestCase(TestCase):
    """Tests for _get_field_definitions method."""

    def test_extracts_field_types(self):
        """Should extract field type names."""
        form = ContactForm()
        proxy = GlueFormProxy(
            target=form,
            unique_name='contact_form',
            access=GlueAccess.VIEW,
        )
        fields = proxy._get_field_definitions()

        self.assertEqual(fields['name']['type'], 'CharField')
        self.assertEqual(fields['email']['type'], 'EmailField')
        self.assertEqual(fields['message']['type'], 'CharField')
        self.assertEqual(fields['priority']['type'], 'ChoiceField')

    def test_extracts_required_flag(self):
        """Should extract required flag for each field."""
        form = ContactForm()
        proxy = GlueFormProxy(
            target=form,
            unique_name='contact_form',
            access=GlueAccess.VIEW,
        )
        fields = proxy._get_field_definitions()

        self.assertTrue(fields['name']['required'])
        self.assertTrue(fields['email']['required'])

    def test_extracts_labels(self):
        """Should extract field labels, falling back to field name if None."""
        form = ContactForm()
        proxy = GlueFormProxy(
            target=form,
            unique_name='contact_form',
            access=GlueAccess.VIEW,
        )
        fields = proxy._get_field_definitions()

        # Default labels are field names when not explicitly set
        self.assertEqual(fields['name']['label'], 'name')
        self.assertEqual(fields['email']['label'], 'email')

    def test_extracts_widget_type(self):
        """Should extract widget class name."""
        form = ContactForm()
        proxy = GlueFormProxy(
            target=form,
            unique_name='contact_form',
            access=GlueAccess.VIEW,
        )
        fields = proxy._get_field_definitions()

        self.assertEqual(fields['message']['widget'], 'Textarea')

    def test_extracts_choices(self):
        """Should extract choices for choice fields."""
        form = ContactForm()
        proxy = GlueFormProxy(
            target=form,
            unique_name='contact_form',
            access=GlueAccess.VIEW,
        )
        fields = proxy._get_field_definitions()

        self.assertIn('choices', fields['priority'])
        self.assertEqual(len(fields['priority']['choices']), 3)

    def test_extracts_max_length(self):
        """Should extract max_length if present."""
        form = ContactForm()
        proxy = GlueFormProxy(
            target=form,
            unique_name='contact_form',
            access=GlueAccess.VIEW,
        )
        fields = proxy._get_field_definitions()

        self.assertEqual(fields['name']['max_length'], 100)


class GlueFormProxyInitialValuesTestCase(TestCase):
    """Tests for _get_initial_values method."""

    def test_returns_empty_values_for_new_form(self):
        """Should return None for fields without initial values."""
        form = ContactForm()
        proxy = GlueFormProxy(
            target=form,
            unique_name='contact_form',
            access=GlueAccess.VIEW,
        )
        values = proxy._get_initial_values()

        self.assertIsNone(values['name'])
        self.assertIsNone(values['email'])

    def test_returns_initial_values_from_form(self):
        """Should return initial values passed to form."""
        form = ContactForm(initial={'name': 'John', 'email': 'john@example.com'})
        proxy = GlueFormProxy(
            target=form,
            unique_name='contact_form',
            access=GlueAccess.VIEW,
        )
        values = proxy._get_initial_values()

        self.assertEqual(values['name'], 'John')
        self.assertEqual(values['email'], 'john@example.com')

    def test_returns_instance_values_for_model_form(self):
        """Should return instance values for ModelForm."""
        task = Task.objects.create(
            title='Test Task',
            description='Test description',
            done=False,
            order=1
        )
        form = TaskForm(instance=task)
        proxy = GlueFormProxy(
            target=form,
            unique_name='task_form',
            access=GlueAccess.VIEW,
        )
        values = proxy._get_initial_values()

        self.assertEqual(values['title'], 'Test Task')
        self.assertEqual(values['description'], 'Test description')
        self.assertEqual(values['done'], False)
        self.assertEqual(values['order'], 1)


class GlueFormProxySessionDataTestCase(TestCase):
    """Tests for session data serialization."""

    def test_includes_form_class_path(self):
        """Should include full form class path in session data."""
        form = ContactForm()
        proxy = GlueFormProxy(
            target=form,
            unique_name='contact_form',
            access=GlueAccess.VIEW,
        )
        session_data = proxy.to_session_data()

        self.assertEqual(
            session_data['form_class_path'],
            'test_project.task.forms.ContactForm'
        )

    def test_includes_initial_values(self):
        """Should include initial values in session data."""
        form = ContactForm(initial={'name': 'John'})
        proxy = GlueFormProxy(
            target=form,
            unique_name='contact_form',
            access=GlueAccess.VIEW,
        )
        session_data = proxy.to_session_data()

        self.assertEqual(session_data['initial']['name'], 'John')

    def test_includes_instance_pk_for_model_form(self):
        """Should include instance pk for ModelForm with instance."""
        task = Task.objects.create(
            title='Test',
            description='Desc',
            done=False,
            order=1
        )
        form = TaskForm(instance=task)
        proxy = GlueFormProxy(
            target=form,
            unique_name='task_form',
            access=GlueAccess.VIEW,
        )
        session_data = proxy.to_session_data()

        self.assertEqual(session_data['instance_pk'], task.pk)


class GlueFormProxyContextDataTestCase(TestCase):
    """Tests for context data serialization."""

    def test_includes_fields(self):
        """Should include field definitions in context data."""
        form = ContactForm()
        proxy = GlueFormProxy(
            target=form,
            unique_name='contact_form',
            access=GlueAccess.VIEW,
        )
        context_data = proxy.to_context_data()

        self.assertIn('fields', context_data)
        self.assertIn('name', context_data['fields'])

    def test_includes_initial(self):
        """Should include initial values in context data."""
        form = ContactForm(initial={'name': 'John'})
        proxy = GlueFormProxy(
            target=form,
            unique_name='contact_form',
            access=GlueAccess.VIEW,
        )
        context_data = proxy.to_context_data()

        self.assertIn('initial', context_data)
        self.assertEqual(context_data['initial']['name'], 'John')

    def test_includes_actions(self):
        """Should include available actions in context data."""
        form = ContactForm()
        proxy = GlueFormProxy(
            target=form,
            unique_name='contact_form',
            access=GlueAccess.VIEW,
        )
        context_data = proxy.to_context_data()

        self.assertIn('actions', context_data)
        self.assertIn('get', context_data['actions'])
        self.assertIn('validate', context_data['actions'])
        self.assertIn('submit', context_data['actions'])
