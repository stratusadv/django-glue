"""
Tests for Django Glue shortcuts (Glue API entry point).
"""
from django.test import TestCase, RequestFactory

from django_glue.shortcuts.glue import Glue
from django_glue.shortcuts.urls import django_glue_urls
from django_glue.access.access import GlueAccess
from django_glue.session import GlueSession
from django_glue.proxies.model.instance.proxy import GlueModelInstanceProxy
from django_glue.proxies.queryset.proxy import GlueQuerySetProxy
from django_glue.proxies.form.proxy import GlueFormProxy
from test_project.gorilla.models import Gorilla
from test_project.test_forms import ContactForm
from django_glue.tests.conftest import MockSession


class GlueModelTestCase(TestCase):
    """Tests for Glue.model() static method."""

    def setUp(self):
        self.factory = RequestFactory()
        self.gorilla = Gorilla.objects.create(
            name='Test Gorilla',
            description='Test',
            age=25,
            weight=350.0,
            height=1.8
        )
        self.request = self.factory.get('/')
        self.request.session = MockSession()

    def test_model_registers_proxy_in_session(self):
        """Glue.model should register the proxy in the session."""
        Glue.model(
            request=self.request,
            unique_name='gorilla',
            target=self.gorilla,
            access=GlueAccess.VIEW,
        )

        session = GlueSession(self.request)
        self.assertIn('gorilla', session.proxy_registry)

    def test_model_sets_proxy_definitions(self):
        """Glue.model should set proxy definitions on the request."""
        Glue.model(
            request=self.request,
            unique_name='gorilla',
            target=self.gorilla,
            access=GlueAccess.CHANGE,
        )

        self.assertTrue(hasattr(self.request, '__glue_proxy_definitions__'))
        self.assertIn('gorilla', self.request.__glue_proxy_definitions__)

    def test_model_proxy_definitions_includes_subject_type(self):
        """Glue.model proxy definitions should include Model subject type."""
        Glue.model(
            request=self.request,
            unique_name='gorilla',
            target=self.gorilla,
            access=GlueAccess.VIEW,
        )

        context = self.request.__glue_proxy_definitions__['gorilla']
        self.assertEqual(context['subject_type'], 'Model')

    def test_model_with_fields_filter(self):
        """Glue.model should accept fields parameter."""
        Glue.model(
            request=self.request,
            unique_name='gorilla',
            target=self.gorilla,
            access=GlueAccess.VIEW,
            fields=['name', 'age'],
        )

        context = self.request.__glue_proxy_definitions__['gorilla']
        field_names = list(context['fields'].keys())
        self.assertIn('name', field_names)
        self.assertIn('age', field_names)

    def test_model_with_exclude_filter(self):
        """Glue.model should accept exclude parameter."""
        Glue.model(
            request=self.request,
            unique_name='gorilla',
            target=self.gorilla,
            access=GlueAccess.VIEW,
            exclude=['description', 'weight'],
        )

        context = self.request.__glue_proxy_definitions__['gorilla']
        field_names = list(context['fields'].keys())
        self.assertNotIn('description', field_names)
        self.assertNotIn('weight', field_names)

    def test_model_default_access_is_view(self):
        """Glue.model should default to VIEW access."""
        Glue.model(
            request=self.request,
            unique_name='gorilla',
            target=self.gorilla,
        )

        session = GlueSession(self.request)
        self.assertEqual(session.proxy_registry['gorilla'], GlueAccess.VIEW)


class GlueQuerySetTestCase(TestCase):
    """Tests for Glue.queryset() static method."""

    def setUp(self):
        self.factory = RequestFactory()
        self.gorilla = Gorilla.objects.create(
            name='Test Gorilla',
            description='Test',
            age=25,
            weight=350.0,
            height=1.8
        )
        self.request = self.factory.get('/')
        self.request.session = MockSession()

    def test_queryset_registers_proxy_in_session(self):
        """Glue.queryset should register the proxy in the session."""
        Glue.queryset(
            request=self.request,
            unique_name='gorillas',
            target=Gorilla.objects.all(),
            access=GlueAccess.VIEW,
        )

        session = GlueSession(self.request)
        self.assertIn('gorillas', session.proxy_registry)

    def test_queryset_sets_proxy_definitions(self):
        """Glue.queryset should set proxy definitions on the request."""
        Glue.queryset(
            request=self.request,
            unique_name='gorillas',
            target=Gorilla.objects.all(),
            access=GlueAccess.CHANGE,
        )

        self.assertTrue(hasattr(self.request, '__glue_proxy_definitions__'))
        self.assertIn('gorillas', self.request.__glue_proxy_definitions__)

    def test_queryset_proxy_definitions_includes_subject_type(self):
        """Glue.queryset proxy definitions should include QuerySet subject type."""
        Glue.queryset(
            request=self.request,
            unique_name='gorillas',
            target=Gorilla.objects.all(),
            access=GlueAccess.VIEW,
        )

        context = self.request.__glue_proxy_definitions__['gorillas']
        self.assertEqual(context['subject_type'], 'QuerySet')


class GlueFormTestCase(TestCase):
    """Tests for Glue.form() static method."""

    def setUp(self):
        self.factory = RequestFactory()
        self.request = self.factory.get('/')
        self.request.session = MockSession()

    def test_form_with_regular_form_registers_as_form_proxy(self):
        """Glue.form with regular Form should register as GlueFormProxy."""
        form = ContactForm()
        Glue.form(
            request=self.request,
            unique_name='contact_form',
            target=form,
            access=GlueAccess.CHANGE,
        )

        context = self.request.__glue_proxy_definitions__['contact_form']
        self.assertEqual(context['subject_type'], 'BaseForm')

    def test_form_with_modelform_registers_as_model_proxy(self):
        """Glue.form with ModelForm should register as GlueModelProxy."""
        from test_project.test_forms import TestModelForm
        gorilla = Gorilla.objects.create(
            name='Test Gorilla',
            description='Test',
            age=25,
            weight=350.0,
            height=1.8
        )
        form = TestModelForm(instance=gorilla)
        Glue.form(
            request=self.request,
            unique_name='gorilla_form',
            target=form,
            access=GlueAccess.CHANGE,
        )

        context = self.request.__glue_proxy_definitions__['gorilla_form']
        self.assertEqual(context['subject_type'], 'Model')

    def test_form_with_new_modelform_creates_blank_instance(self):
        """Glue.form with new ModelForm should create a blank model instance."""
        from test_project.test_forms import TestModelForm
        form = TestModelForm()
        Glue.form(
            request=self.request,
            unique_name='gorilla_form',
            target=form,
            access=GlueAccess.CHANGE,
        )

        context = self.request.__glue_proxy_definitions__['gorilla_form']
        self.assertEqual(context['subject_type'], 'Model')
        self.assertIsNone(context['target_pk'])


class DjangoGlueUrlsTestCase(TestCase):
    """Tests for django_glue_urls() helper."""

    def test_returns_list_of_paths(self):
        """django_glue_urls should return a list of URL patterns."""
        urls = django_glue_urls()
        self.assertIsInstance(urls, list)
        self.assertEqual(len(urls), 1)
