"""
Tests for GlueFormProxy submit() action.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_project.base_settings')
django.setup()

from django.test import TestCase

from django_glue.access.access import GlueAccess
from django_glue.proxies.form.proxy import GlueFormProxy
from django_glue.exceptions import GlueAccessError
from django_glue import data_transfer_objects as dto
from test_project.task.forms import TaskForm, ContactForm
from test_project.task.models import Task


class GlueFormProxySubmitTestCase(TestCase):
    """Tests for GlueFormProxy.submit() action."""

    def test_submit_returns_success_true_for_valid_data(self):
        """submit() should return success=True for valid data."""
        form = ContactForm()
        proxy = GlueFormProxy(
            target=form,
            unique_name='contact_form',
            access=GlueAccess.CHANGE,
        )
        result = proxy.submit({
            'name': 'John Doe',
            'email': 'john@example.com',
            'message': 'Hello world',
            'priority': 'medium',
        })

        self.assertTrue(result['success'])
        self.assertEqual(result['errors'], {})

    def test_submit_returns_success_false_for_invalid_data(self):
        """submit() should return success=False for invalid data."""
        form = ContactForm()
        proxy = GlueFormProxy(
            target=form,
            unique_name='contact_form',
            access=GlueAccess.CHANGE,
        )
        result = proxy.submit({
            'name': '',
            'email': 'invalid',
            'message': '',
            'priority': 'medium',
        })

        self.assertFalse(result['success'])
        self.assertIn('name', result['errors'])

    def test_submit_returns_cleaned_data_for_regular_form(self):
        """submit() should return cleaned_data for regular Form."""
        form = ContactForm()
        proxy = GlueFormProxy(
            target=form,
            unique_name='contact_form',
            access=GlueAccess.CHANGE,
        )
        result = proxy.submit({
            'name': 'John Doe',
            'email': 'john@example.com',
            'message': 'Hello world',
            'priority': 'high',
        })

        self.assertIn('data', result)
        self.assertEqual(result['data']['name'], 'John Doe')
        self.assertEqual(result['data']['priority'], 'high')

    def test_submit_saves_model_form(self):
        """submit() should save ModelForm and create instance."""
        form = TaskForm()
        proxy = GlueFormProxy(
            target=form,
            unique_name='task_form',
            access=GlueAccess.CHANGE,
        )

        initial_count = Task.objects.count()

        result = proxy.submit({
            'title': 'New Task',
            'description': 'Task description',
            'done': False,
            'order': 1,
        })

        self.assertTrue(result['success'])
        self.assertEqual(Task.objects.count(), initial_count + 1)
        self.assertIn('id', result['data'])

    def test_submit_updates_existing_model_form_instance(self):
        """submit() should update existing instance for ModelForm."""
        task = Task.objects.create(
            title='Original Title',
            description='Original description',
            done=False,
            order=1
        )
        form = TaskForm(instance=task)
        proxy = GlueFormProxy(
            target=form,
            unique_name='task_form',
            access=GlueAccess.CHANGE,
        )

        result = proxy.submit({
            'title': 'Updated Title',
            'description': 'Updated description',
            'done': True,
            'order': 2,
        })

        self.assertTrue(result['success'])
        self.assertEqual(result['data']['id'], task.pk)

        task.refresh_from_db()
        self.assertEqual(task.title, 'Updated Title')
        self.assertEqual(task.done, True)

    def test_submit_requires_change_access(self):
        """submit() should require CHANGE access."""
        form = ContactForm()
        proxy = GlueFormProxy(
            target=form,
            unique_name='contact_form',
            access=GlueAccess.VIEW,
        )

        action_data = dto.GlueActionRequestData(
            unique_name='contact_form',
            action='submit',
            payload={'name': 'Test'}
        )

        with self.assertRaises(GlueAccessError):
            proxy.process_action(action_data)

    def test_submit_works_with_delete_access(self):
        """submit() should work with DELETE access (cascading)."""
        form = ContactForm()
        proxy = GlueFormProxy(
            target=form,
            unique_name='contact_form',
            access=GlueAccess.DELETE,
        )
        result = proxy.submit({
            'name': 'John Doe',
            'email': 'john@example.com',
            'message': 'Hello world',
            'priority': 'medium',
        })

        self.assertTrue(result['success'])


class GlueFormProxyFromRegistryDataTestCase(TestCase):
    """Tests for from_proxy_registry_data class method."""

    def test_reconstructs_form_from_class_path(self):
        """Should reconstruct form from stored class path."""
        proxy = GlueFormProxy.from_proxy_registry_data(
            form_class_path='test_project.task.forms.ContactForm',
            initial={'name': 'John'},
            access=GlueAccess.VIEW,
            unique_name='contact_form',
        )

        self.assertIsInstance(proxy, GlueFormProxy)
        self.assertEqual(proxy.target.__class__.__name__, 'ContactForm')

    def test_reconstructs_model_form_with_instance(self):
        """Should reconstruct ModelForm with instance from pk."""
        task = Task.objects.create(
            title='Test Task',
            description='Description',
            done=False,
            order=1
        )

        proxy = GlueFormProxy.from_proxy_registry_data(
            form_class_path='test_project.task.forms.TaskForm',
            initial={},
            instance_pk=task.pk,
            access=GlueAccess.CHANGE,
            unique_name='task_form',
        )

        self.assertIsInstance(proxy, GlueFormProxy)
        self.assertEqual(proxy.target.instance.pk, task.pk)

    def test_reconstructs_model_form_without_instance(self):
        """Should reconstruct ModelForm without instance when pk is None."""
        proxy = GlueFormProxy.from_proxy_registry_data(
            form_class_path='test_project.task.forms.TaskForm',
            initial={},
            instance_pk=None,
            access=GlueAccess.CHANGE,
            unique_name='task_form',
        )

        self.assertIsInstance(proxy, GlueFormProxy)
        self.assertIsNone(proxy.target.instance.pk)
