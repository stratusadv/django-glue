from __future__ import annotations

import json

from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.test import RequestFactory, TestCase, override_settings

from django_glue.glue.context import GlueContextManager
from django_glue.glue.objects.django.template import TemplateGlue
from django_glue.glue.policy import GluePolicy
from django_glue.resolver.view_fragment.resolver import GlueViewFragmentResolver
from django_glue.response import GlueTemplateResponse
from django_glue.tests.conftest import MockSession


class GlueHtmlResponseTestCase(TestCase):
    def setUp(self) -> None:
        self.request = RequestFactory().get('/')
        self.request.session = MockSession()

    def test_view_and_attribute_share_rendered_html_and_manifests(self) -> None:
        response = TemplateResponse(
            self.request,
            'glue_template_test.html',
            {'greeting': 'Shared HTML'},
        )
        child = TemplateGlue(
            'glue_template_test.html',
            name='child',
        )
        def register_child(_rendered: TemplateResponse) -> None:
            GlueContextManager(self.request).add_glue(child)

        response.add_post_render_callback(register_child)

        attribute_result = GlueTemplateResponse.from_template_response(response).result
        resolver = GlueViewFragmentResolver()
        resolver.setup(self.request)
        view_result = json.loads(resolver._render_response(response).content)

        assert view_result.keys() == attribute_result.keys()
        assert view_result['html'] == attribute_result['html']
        assert view_result['is_glue_template_response'] is True
        assert 'Shared HTML' in view_result['html']
        assert len(view_result['manifest_list']) == 1
        assert len(attribute_result['manifest_list']) == 1
        for payload in (view_result, attribute_result):
            assert GluePolicy.from_token(payload['manifest_list'][0]['policy_token']).name == 'child'

    def test_plain_view_response_uses_its_declared_charset(self) -> None:
        resolver = GlueViewFragmentResolver()
        resolver.setup(self.request)
        response = HttpResponse(
            'café',
            content_type='text/html; charset=iso-8859-1',
        )

        result = json.loads(resolver._render_response(response).content)

        assert result == {
            'is_glue_template_response': True,
            'html': 'café',
            'manifest_list': [],
        }

    @override_settings(TEMPLATES=[{
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'OPTIONS': {
            'loaders': [('django.template.loaders.locmem.Loader', {
                'card.html': '<div>{{ greeting }}{% csrf_token %}</div>',
            })],
        },
    }])
    def test_template_proxy_uses_request_context_and_html_envelope(self) -> None:
        template = TemplateGlue(
            'card.html',
            name='card',
            initial_context_data={'greeting': 'Initial'},
        )
        template.request = self.request

        result = template.render_html({'greeting': 'Updated'}).result

        assert result['is_glue_template_response'] is True
        assert 'Updated' in result['html']
        assert 'Initial' not in result['html']
        assert 'csrfmiddlewaretoken' in result['html']
        assert result['manifest_list'] == []
