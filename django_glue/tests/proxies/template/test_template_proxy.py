"""
Tests for GlueTemplateProxy.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_project.settings')
django.setup()

from django.test import TestCase

from django_glue.access.access import GlueAccess
from django_glue.proxies import GlueTemplateProxy
from django_glue.resolver.action.schemas import ActionRequest
from django_glue.exceptions import GlueError


class GlueTemplateProxyInitTestCase(TestCase):
    """Tests for GlueTemplateProxy initialization."""

    def test_stores_template_name(self):
        proxy = GlueTemplateProxy(
            target='base.html',
            unique_name='my_template',
            access=GlueAccess.VIEW,
        )

        self.assertEqual(proxy.template_name, 'base.html')
        self.assertEqual(proxy.unique_name, 'my_template')

    def test_stores_definition_context_data(self):
        proxy = GlueTemplateProxy(
            target='base.html',
            unique_name='my_template',
            access=GlueAccess.VIEW,
            definition_context_data={'foo': 'bar'},
        )

        self.assertEqual(proxy._context_data, {'foo': 'bar'})

    def test_defaults_definition_context_data_to_empty_dict(self):
        proxy = GlueTemplateProxy(
            target='base.html',
            unique_name='my_template',
            access=GlueAccess.VIEW,
        )

        self.assertEqual(proxy._context_data, {})

    def test_raises_for_non_string_target(self):
        with self.assertRaises(ValueError):
            GlueTemplateProxy(
                target=123,
                unique_name='bad',
                access=GlueAccess.VIEW,
            )


class GlueTemplateProxyContextDataTestCase(TestCase):
    """Tests for GlueTemplateProxy.to_proxy_definition()."""

    def test_to_proxy_definition_includes_subject_type_template(self):
        proxy = GlueTemplateProxy(
            target='base.html',
            unique_name='my_template',
            access=GlueAccess.VIEW,
        )

        context_data = proxy.to_contract()

        self.assertEqual(context_data['subject_type'], 'Template')

    def test_to_proxy_definition_includes_template_name(self):
        proxy = GlueTemplateProxy(
            target='components/card.html',
            unique_name='card',
            access=GlueAccess.VIEW,
            definition_context_data={'greeting': 'Hello'},
        )

        context_data = proxy.to_contract()

        self.assertEqual(context_data['template_name'], 'components/card.html')
        self.assertEqual(context_data['definition_context_data'], {'greeting': 'Hello'})

    def test_to_proxy_definition_includes_actions(self):
        proxy = GlueTemplateProxy(
            target='base.html',
            unique_name='my_template',
            access=GlueAccess.VIEW,
        )

        context_data = proxy.to_contract()

        self.assertIn('actions', context_data)
        self.assertIn('render_html', context_data['actions'])


class GlueTemplateProxyRenderHtmlTestCase(TestCase):
    """Tests for GlueTemplateProxy.render_html() action."""

    def test_render_html_with_simple_template(self):
        proxy = GlueTemplateProxy(
            target='glue_template_test.html',
            unique_name='test',
            access=GlueAccess.VIEW,
        )

        action_data = ActionRequest(proxy_definition={}, action_kwargs={})
        result = proxy.render_html(action_data)

        self.assertIn('html', result)
        self.assertIsInstance(result['html'], str)

    def test_render_html_merges_definition_context_data_with_action_kwargs(self):
        proxy = GlueTemplateProxy(
            target='glue_template_test.html',
            unique_name='test',
            access=GlueAccess.VIEW,
            definition_context_data={'greeting': 'Default'},
        )

        action_data = ActionRequest(
            proxy_definition={},
            action_kwargs={'greeting': 'Override'},
        )
        result = proxy.render_html(action_data)

        self.assertIn('html', result)
        self.assertIn('Override', result['html'])
        self.assertNotIn('Default', result['html'])

    def test_render_html_with_view_access(self):
        proxy = GlueTemplateProxy(
            target='glue_template_test.html',
            unique_name='test',
            access=GlueAccess.VIEW,
        )

        action_data = ActionRequest(proxy_definition={}, action_kwargs={})

        result = proxy.process_action('render_html', action_data)
        self.assertIn('html', result)

    def test_render_html_with_higher_access(self):
        for access in [GlueAccess.CHANGE, GlueAccess.DELETE]:
            proxy = GlueTemplateProxy(
                target='glue_template_test.html',
                unique_name='test',
                access=access,
            )

            action_data = ActionRequest(proxy_definition={}, action_kwargs={})
            result = proxy.process_action('render_html', action_data)
            self.assertIn('html', result)

    def test_render_html_raises_for_missing_template(self):
        proxy = GlueTemplateProxy(
            target='nonexistent/missing.html',
            unique_name='missing',
            access=GlueAccess.VIEW,
        )

        action_data = ActionRequest(proxy_definition={}, action_kwargs={})

        with self.assertRaises(GlueError) as context:
            proxy.render_html(action_data)

        self.assertIn('Template not found', str(context.exception))

    def test_render_html_with_no_action_kwargs(self):
        proxy = GlueTemplateProxy(
            target='glue_template_test.html',
            unique_name='test',
            access=GlueAccess.VIEW,
            context_data={'greeting': 'Hello'},
        )

        action_data = ActionRequest(proxy_definition={})
        result = proxy.render_html(action_data)

        self.assertIn('html', result)
        self.assertIn('Hello', result['html'])

    def test_render_html_definition_context_data_overrides(self):
        """action_kwargs should override definition_context_data values."""
        proxy = GlueTemplateProxy(
            target='glue_template_test.html',
            unique_name='test',
            access=GlueAccess.VIEW,
            definition_context_data={'greeting': 'Backend', 'extra': 'kept'},
        )

        action_data = ActionRequest(
            proxy_definition={},
            action_kwargs={'greeting': 'Frontend'},
        )
        result = proxy.render_html(action_data)

        self.assertIn('Frontend', result['html'])
        self.assertNotIn('Backend', result['html'])


class GlueTemplateProxyFromActionRequestDataTestCase(TestCase):
    """Tests for GlueTemplateProxy.from_action_request_data()."""

    def test_from_action_request_data_reconstructs_proxy(self):
        proxy = GlueTemplateProxy.from_action_request_data(
            template_name='base.html',
            definition_context_data={'foo': 'bar'},
            access=GlueAccess.VIEW,
            unique_name='my_template',
        )

        self.assertEqual(proxy.template_name, 'base.html')
        self.assertEqual(proxy._context_data, {'foo': 'bar'})
        self.assertEqual(proxy.unique_name, 'my_template')
        self.assertEqual(proxy.access, GlueAccess.VIEW)

    def test_from_action_request_data_defaults_definition_context_data(self):
        proxy = GlueTemplateProxy.from_action_request_data(
            template_name='base.html',
            access=GlueAccess.VIEW,
            unique_name='my_template',
        )

        self.assertEqual(proxy._context_data, {})


class GlueTemplateProxyProcessActionAccessTestCase(TestCase):
    """Tests for access control on GlueTemplateProxy actions."""

    def test_render_html_requires_view_access(self):
        proxy = GlueTemplateProxy(
            target='glue_template_test.html',
            unique_name='test',
            access=GlueAccess.VIEW,
        )

        action_data = ActionRequest(proxy_definition={}, action_kwargs={})
        result = proxy.process_action('render_html', action_data)

        self.assertIn('html', result)
