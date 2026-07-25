"""
Tests for Django Glue template tags.
"""
from django.test import TestCase, RequestFactory, override_settings
from django.template import Template, Context

from django_glue.shortcuts.glue import Glue
from django_glue.access import GlueAccess
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
        self.assertIn(constants.__VERSION__, rendered)

    def test_tag_includes_urls(self):
        """Tag should include URL mappings in the manifest."""
        template = Template('{% load django_glue %}{% django_glue_init %}{{ DJANGO_GLUE_CONTEXT }}')
        context = Context({'request': self.request})

        rendered = template.render(context)
        self.assertIn('callable_attribute', rendered)
        self.assertIn('/__dg__/callable_attribute/', rendered)
        self.assertIn('/__dg__/glue_view/', rendered)

    @override_settings(DJANGO_GLUE_REQUEST_TIMEOUT_SECONDS=45)
    def test_tag_includes_server_defined_client_config(self):
        """Tag should include client config from Django settings in the manifest."""
        template = Template('{% load django_glue %}{% django_glue_init %}{{ DJANGO_GLUE_CONTEXT }}')
        context = Context({'request': self.request})

        rendered = template.render(context)
        self.assertIn('requestTimeoutSeconds', rendered)
        self.assertIn('45', rendered)

    def test_tag_includes_manifest(self):
        """Tag should include manifest data."""
        Glue.model(
            request=self.request,
            unique_name='gorilla',
            target=self.gorilla,
            access=GlueAccess.VIEW,
            fields=['name'],
        )

        template = Template('{% load django_glue %}{% django_glue_init %}{{ DJANGO_GLUE_CONTEXT }}')
        context = Context({'request': self.request})

        rendered = template.render(context)
        self.assertIn('gorilla', rendered)

    def test_tag_includes_manifest_payloads(self):
        """Tag should include manifest payloads when glue objects are registered."""
        Glue.model(
            request=self.request,
            unique_name='gorilla',
            target=self.gorilla,
            access=GlueAccess.VIEW,
            fields=['name'],
        )

        template = Template('{% load django_glue %}{% django_glue_init %}{{ DJANGO_GLUE_CONTEXT }}')
        context = Context({'request': self.request})

        rendered = template.render(context)
        self.assertIn('gorilla', rendered)

    def test_tag_with_no_manifest_registered(self):
        """Tag should work when no glue objects are registered."""
        template = Template('{% load django_glue %}{% django_glue_init %}{{ DJANGO_GLUE_CONTEXT }}')
        context = Context({'request': self.request})

        rendered = template.render(context)
        self.assertIn('manifest_list', rendered)
        self.assertIn('[]', rendered)


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


class GlueFieldPathFilterTestCase(TestCase):
    """Tests for field path filters used by Glue field components."""

    def test_glue_field_value_path_removes_fields_namespace(self):
        template = Template(
            '{% load django_glue %}{{ path|glue_field_value_path }}'
        )

        rendered = template.render(
            Context({'path': 'gorilla.$fields.name'})
        ).strip()

        self.assertEqual(rendered, 'gorilla.name')

    def test_glue_field_metadata_path_adds_fields_namespace(self):
        template = Template(
            '{% load django_glue %}{{ path|glue_field_metadata_path }}'
        )

        rendered = template.render(Context({'path': 'gorilla.name'})).strip()

        self.assertEqual(rendered, 'gorilla.$fields.name')

    def test_glue_field_metadata_path_preserves_existing_namespace(self):
        template = Template(
            '{% load django_glue %}{{ path|glue_field_metadata_path }}'
        )

        rendered = template.render(
            Context({'path': 'gorilla.$fields.name'})
        ).strip()

        self.assertEqual(rendered, 'gorilla.$fields.name')
