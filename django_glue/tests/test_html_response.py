from __future__ import annotations

import json

from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.test import RequestFactory, TestCase

from django_glue.access import GlueAccess
from django_glue.constants import GLUE_VIEW_MEDIA_TYPE
from django_glue.glue.base import BaseGlue
from django_glue.glue.context import GlueContextManager
from django_glue.glue.policy import GluePolicy
from django_glue.middleware import GlueViewMiddleware
from django_glue.response import GlueTemplateResponse
from django_glue.tests.conftest import MockSession


class RenderedChildGlue(BaseGlue):
    namespace = 'renderedChild'

    @classmethod
    def _reconstruct_from_policy(cls, policy: GluePolicy) -> RenderedChildGlue:
        return cls(name=policy.name, access=policy.access)


class GlueHtmlResponseTestCase(TestCase):
    def setUp(self) -> None:
        self.request = RequestFactory().get('/', HTTP_ACCEPT=GLUE_VIEW_MEDIA_TYPE)
        self.request.session = MockSession()

    def test_view_and_attribute_share_rendered_html_and_objects(self) -> None:
        response = TemplateResponse(
            self.request,
            'glue_template_test.html',
            {'greeting': 'Shared HTML'},
        )
        child = RenderedChildGlue(name='child', access=GlueAccess.VIEW)

        def register_child(_rendered: TemplateResponse) -> None:
            GlueContextManager(self.request).add_glue(child)

        response.add_post_render_callback(register_child)

        attribute_response = GlueTemplateResponse.from_template_response(response)
        view_result = json.loads(GlueViewMiddleware(lambda _request: response)(self.request).content)

        assert view_result['is_glue_template_response'] is True
        assert view_result['html'] == attribute_response.html
        assert 'Shared HTML' in view_result['html']
        assert len(view_result['objects']) == 1
        assert len(attribute_response.objects) == 1
        for objects in (view_result['objects'], attribute_response.objects):
            assert GluePolicy.from_token(objects[0]['policy_token']).name == 'child'

    def test_plain_view_response_uses_its_declared_charset(self) -> None:
        response = HttpResponse('café', content_type='text/html; charset=iso-8859-1')

        result = json.loads(GlueViewMiddleware(lambda _request: response)(self.request).content)

        assert result == {'is_glue_template_response': True, 'html': 'café', 'objects': []}
