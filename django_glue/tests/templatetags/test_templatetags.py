"""
Tests for Django Glue template tags.
"""
from django.test import TestCase, RequestFactory, override_settings
from django.template import Template, Context

from django_glue.shortcuts.glue import Glue
from django_glue.access.access import GlueAccess
from django_glue import constants
from test_project.gorilla.models import Gorilla
from django_glue.tests.conftest import MockSession


class DjangoGlueInitTagTestCase(TestCase):
    """Tests for {% django_glue_init %} template tag."""

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

    def test_tag_includes_version(self):
        """Tag should include the Django Glue version."""
        template = Template('{% load django_glue %}{% django_glue_init %}{{ DJANGO_GLUE_VERSION }}')
        context = Context({'request': self.request})

        # The tag populates context variables
        rendered = template.render(context)
        self.assertIn('1.0.0a1', rendered)

    def test_tag_includes_urls(self):
        """Tag should include URL mappings."""
        template = Template('{% load django_glue %}{% django_glue_init %}{{ DJANGO_GLUE_URLS }}')
        context = Context({'request': self.request})

        rendered = template.render(context)
        self.assertIn('__dg__', rendered)

    def test_tag_includes_keep_live_interval(self):
        """Tag should include keep-alive interval."""
        template = Template('{% load django_glue %}{% django_glue_init %}{{ DJANGO_GLUE_KEEP_LIVE_INTERVAL_TIME_MILLISECONDS }}')
        context = Context({'request': self.request})

        rendered = template.render(context)
        self.assertIn('600', rendered)

    def test_tag_includes_proxy_registry(self):
        """Tag should include proxy registry data."""
        Glue.model(
            request=self.request,
            unique_name='gorilla',
            target=self.gorilla,
            access=GlueAccess.VIEW,
        )

        template = Template('{% load django_glue %}{% django_glue_init %}{{ DJANGO_GLUE_SESSION_PROXY_REGISTRY }}')
        context = Context({'request': self.request})

        rendered = template.render(context)
        self.assertIn('gorilla', rendered)

    def test_tag_includes_proxy_context_data(self):
        """Tag should include proxy context data when proxies are registered."""
        Glue.model(
            request=self.request,
            unique_name='gorilla',
            target=self.gorilla,
            access=GlueAccess.VIEW,
        )

        template = Template('{% load django_glue %}{% django_glue_init %}{{ DJANGO_GLUE_PROXIES_CONTEXT_DATA }}')
        context = Context({'request': self.request})

        rendered = template.render(context)
        self.assertIn('gorilla', rendered)

    def test_tag_with_no_proxies_registered(self):
        """Tag should work when no proxies are registered."""
        template = Template('{% load django_glue %}{% django_glue_init %}{{ DJANGO_GLUE_PROXIES_CONTEXT_DATA }}')
        context = Context({'request': self.request})

        rendered = template.render(context)
        self.assertIn('{}', rendered)


class GetItemFilterTestCase(TestCase):
    """Tests for the get_item template filter."""

    def test_gets_item_from_dict(self):
        """Should retrieve an item from a dictionary."""
        template = Template('{% load utils %}{{ my_dict|get_item:"key" }}')
        context = Context({'my_dict': {'key': 'value'}})

        rendered = template.render(context).strip()
        self.assertEqual(rendered, 'value')

    def test_returns_none_for_missing_key(self):
        """Should return None for a missing key."""
        template = Template('{% load utils %}{{ my_dict|get_item:"missing" }}')
        context = Context({'my_dict': {'key': 'value'}})

        rendered = template.render(context).strip()
        self.assertEqual(rendered, 'None')

    def test_works_with_variable_key(self):
        """Should work with a variable as the key."""
        template = Template('{% load utils %}{{ my_dict|get_item:key_var }}')
        context = Context({'my_dict': {'foo': 'bar'}, 'key_var': 'foo'})

        rendered = template.render(context).strip()
        self.assertEqual(rendered, 'bar')
