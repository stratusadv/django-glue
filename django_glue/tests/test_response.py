from django.template.response import TemplateResponse
from django.test import RequestFactory, TestCase

from django_glue.glue.context import GlueContextManager
from django_glue.glue.json import JsonGlue
from django_glue.message import GlueMessage
from django_glue.response import GlueResponse, GlueTemplateResponse
from django_glue.tests.conftest import MockSession


class GlueResponseTestCase(TestCase):
    def test_stores_result(self):
        response = GlueResponse(result=[[1, 'Chest Pound'], [2, 'Ground Slam']])

        self.assertEqual(response.result, [[1, 'Chest Pound'], [2, 'Ground Slam']])

    def test_default_result_is_none(self):
        response = GlueResponse()

        self.assertIsNone(response.result)

    def test_stores_messages_as_list(self):
        message = GlueMessage(level=GlueMessage.Level.SUCCESS, message='Saved!')

        response = GlueResponse(result={'step': 1}, messages=(message,))

        self.assertEqual(response.messages, [message])

    def test_default_messages_is_empty_list(self):
        response = GlueResponse(result={'valid': True})

        self.assertEqual(response.messages, [])

    def test_stores_status(self):
        response = GlueResponse(result={'created': True}, status=201)

        self.assertEqual(response.status, 201)

    def test_exposes_message_class(self):
        self.assertIs(GlueResponse.Message, GlueMessage)

    def test_constructor_rejects_internal_envelope_fields(self):
        with self.assertRaises(TypeError):
            GlueResponse(result={'valid': True}, state={'errors': {}})

    def test_from_result_returns_same_instance_for_glue_response(self):
        response = GlueResponse(result={'step': 1})

        self.assertIs(GlueResponse.from_result(response), response)

    def test_from_result_wraps_plain_values(self):
        response = GlueResponse.from_result({'created': True})

        self.assertIsInstance(response, GlueResponse)
        self.assertEqual(response.result, {'created': True})

    def test_from_result_rejects_unsupported_http_response_types(self):
        from django.http import HttpResponse

        with self.assertRaises(TypeError):
            GlueResponse.from_result(HttpResponse('raw'))


class GlueTemplateResponseTestCase(TestCase):
    def setUp(self) -> None:
        self.request = RequestFactory().get('/')
        self.request.session = MockSession()

    def test_renders_template_and_marks_result_as_template_response(self):
        response = GlueTemplateResponse(
            self.request,
            'glue_template_test.html',
            {'greeting': 'Hello, Grappler!'},
        )

        self.assertIsInstance(response, GlueResponse)
        self.assertTrue(response.result['is_glue_template_response'])
        self.assertIn('Hello, Grappler!', response.result['html'])

    def test_renders_with_request_context_so_request_dependent_tags_work(self):
        # render_to_string must be given request= (not just context=) or
        # anything that depends on the current request -- {% csrf_token %},
        # RequestContext-based context processors, permission checks -- is
        # silently unavailable in the rendered HTML. glue_template_test.html
        # doesn't itself use csrf_token, so assert on render_to_string's
        # behavior directly: with a request, {% csrf_token %} produces a
        # real hidden input instead of silently rendering empty.
        from django.template import Context, RequestContext, Template

        template = Template('{% csrf_token %}')
        rendered_without_request = template.render(Context({}))
        rendered_with_request = template.render(RequestContext(self.request, {}))

        self.assertEqual(rendered_without_request, '')
        self.assertIn('csrfmiddlewaretoken', rendered_with_request)

    def test_result_carries_manifests_registered_earlier_in_the_request(self):
        glue_object = JsonGlue(42, name='answer')
        GlueContextManager(self.request).add_glue(glue_object)

        response = GlueTemplateResponse(
            self.request,
            'glue_template_test.html',
            {'greeting': 'Hi'},
        )

        manifest_types = [
            manifest['metadata'].get('type')
            for manifest in response.result['manifest_list']
        ]
        self.assertIn('number', manifest_types)

    def test_from_template_response_renders_and_marks_result(self):
        template_response = TemplateResponse(
            self.request,
            'glue_template_test.html',
            {'greeting': 'From a view'},
        )

        response = GlueTemplateResponse.from_template_response(template_response)

        self.assertIsInstance(response, GlueResponse)
        self.assertTrue(response.result['is_glue_template_response'])
        self.assertIn('From a view', response.result['html'])

    def test_from_result_coerces_template_response(self):
        template_response = TemplateResponse(
            self.request,
            'glue_template_test.html',
            {'greeting': 'Coerced'},
        )

        response = GlueResponse.from_result(template_response)

        self.assertTrue(response.result['is_glue_template_response'])
        self.assertIn('Coerced', response.result['html'])
