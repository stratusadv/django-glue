import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_project.settings')
django.setup()

from django.test import RequestFactory, TestCase

from django_glue.access.access import GlueAccess
from django_glue.constants import DJANGO_GLUE_PROXIES_REQUEST_ATTR_KEY
from django_glue.proxies.template.proxy import GlueTemplateProxy
from django_glue.proxies.template.state import GlueTemplateProxyState
from django_glue.resolver.exceptions import GlueResolverError


def make_template_proxy(
    template_path='glue_template_test.html',
    name='test',
    access=GlueAccess.VIEW,
    context_data=None,
):
    return GlueTemplateProxy(
        name=name,
        namespace='template',
        access=access,
        state=GlueTemplateProxyState(
            template_path=template_path,
            context_data=context_data or {},
        ),
    )


class GlueTemplateProxyStateTestCase(TestCase):
    def test_stores_template_path(self):
        proxy = make_template_proxy(template_path='base.html', name='my_template')

        self.assertEqual(proxy.state.template_path, 'base.html')
        self.assertEqual(proxy.name, 'my_template')

    def test_stores_initial_context_data(self):
        proxy = make_template_proxy(context_data={'foo': 'bar'})

        self.assertEqual(proxy.state.context_data, {'foo': 'bar'})

    def test_serializes_runtime_state(self):
        state = GlueTemplateProxyState(template_path='base.html', context_data={'foo': 'bar'})

        self.assertEqual(
            state.serialize(),
            {'namespace': 'template', 'context_data': {'foo': 'bar'}},
        )


class GlueTemplateProxyPolicyTestCase(TestCase):
    def test_custom_policy_details_include_template_path(self):
        proxy = make_template_proxy(template_path='components/card.html', context_data={'greeting': 'Hello'})

        self.assertEqual(proxy._custom_policy_details['template_path'], 'components/card.html')
        self.assertEqual(proxy._custom_policy_details['initial_context_data'], {'greeting': 'Hello'})

    def test_register_policy_serializes_template_details(self):
        request = RequestFactory().get('/')

        GlueTemplateProxy.register_policy(
            request=request,
            target='glue_template_test.html',
            name='card',
            initial_context_data={'greeting': 'Hello'},
        )

        registered = getattr(request, DJANGO_GLUE_PROXIES_REQUEST_ATTR_KEY)['card']
        subject_details = registered['policy']['subject_details']

        self.assertEqual(subject_details['namespace'], 'template')
        self.assertEqual(subject_details['template_path'], 'glue_template_test.html')
        self.assertEqual(subject_details['initial_context_data'], {'greeting': 'Hello'})


class GlueTemplateProxyBoundAttributesTestCase(TestCase):
    def test_discovers_render_html_bound_attribute(self):
        proxy = make_template_proxy()

        bound_attributes = proxy.discover_bound_attributes()

        self.assertIn('GlueTemplateProxy.render_html', bound_attributes)
        self.assertEqual(
            bound_attributes['GlueTemplateProxy.render_html'].required_access,
            GlueAccess.VIEW,
        )

    def test_render_html_with_simple_template(self):
        proxy = make_template_proxy()

        result = proxy.render_html(request=None)

        self.assertIn('html', result)
        self.assertIsInstance(result['html'], str)

    def test_render_html_merges_context_data_with_kwargs(self):
        proxy = make_template_proxy(context_data={'greeting': 'Default'})

        result = proxy.render_html(request=None, greeting='Override')

        self.assertIn('Override', result['html'])
        self.assertNotIn('Default', result['html'])

    def test_render_html_uses_state_context_when_no_kwargs_are_sent(self):
        proxy = make_template_proxy(context_data={'greeting': 'Hello'})

        result = proxy.render_html(request=None)

        self.assertIn('Hello', result['html'])

    def test_render_html_context_kwargs_override_state_context(self):
        proxy = make_template_proxy(context_data={'greeting': 'Backend', 'extra': 'kept'})

        result = proxy.render_html(request=None, greeting='Frontend')

        self.assertIn('Frontend', result['html'])
        self.assertNotIn('Backend', result['html'])

    def test_render_html_raises_for_missing_template(self):
        proxy = make_template_proxy(template_path='nonexistent/missing.html')

        with self.assertRaises(GlueResolverError) as context:
            proxy.render_html(request=None)

        self.assertIn('Template not found', str(context.exception))
