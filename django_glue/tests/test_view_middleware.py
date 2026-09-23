from __future__ import annotations

from django.conf import settings
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse, StreamingHttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings

from django_glue.constants import GLUE_VIEW_MEDIA_TYPE
from django_glue.glue.policy import GluePolicy
from django_glue.middleware import GLUE_VIEW_MIDDLEWARE_PATH, GlueViewMiddleware, check_glue_view_middleware
from django_glue.tests.conftest import MockSession
from test_project.gorilla.models import Gorilla


def negotiate(response, *, accept=GLUE_VIEW_MEDIA_TYPE):
    request = RequestFactory().get('/target/', HTTP_ACCEPT=accept)
    request.session = MockSession()
    return GlueViewMiddleware(lambda _request: response)(request)


class GlueViewMiddlewareTestCase(SimpleTestCase):
    def test_negotiated_html_becomes_the_envelope_and_varies_on_accept(self):
        result = negotiate(HttpResponse('<p>Hi</p>'))

        self.assertEqual(result['Content-Type'], 'application/json')
        self.assertIn('Accept', result['Vary'])
        self.assertEqual(result.content, b'{"is_glue_template_response": true, "html": "<p>Hi</p>", "objects": []}')

    def test_ordinary_html_passes_through_and_still_varies_on_accept(self):
        page = HttpResponse('<p>Hi</p>')

        result = negotiate(page, accept='text/html')

        self.assertIs(result, page)
        self.assertIn('Accept', result['Vary'])

    def test_non_html_redirect_error_and_streaming_responses_pass_through(self):
        streaming = StreamingHttpResponse(iter([b'chunk']), content_type='text/html')
        for response in (
            JsonResponse({'ok': True}),
            HttpResponseRedirect('/elsewhere/'),
            HttpResponse('<p>Missing</p>', status=404),
            streaming,
        ):
            with self.subTest(response=type(response).__name__):
                self.assertIs(negotiate(response), response)
        self.assertEqual(b''.join(streaming.streaming_content), b'chunk')


class BlockTemplatePathMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.endswith('/template/'):
            return HttpResponse('Forbidden', status=403)
        return self.get_response(request)


class GlueViewDispatchTestCase(TestCase):
    def setUp(self):
        self.gorilla = Gorilla.objects.create(name='Koko')

    def test_view_request_runs_the_real_route_and_returns_the_envelope(self):
        response = self.client.get(f'/{self.gorilla.pk}/template/', HTTP_ACCEPT=GLUE_VIEW_MEDIA_TYPE)

        payload = response.json()
        self.assertTrue(payload['is_glue_template_response'])
        self.assertIn('Save Changes', payload['html'])
        policy = GluePolicy.from_token(payload['objects'][0]['policy_token'])
        self.assertEqual((policy.name, policy.state_snapshot['name']), ('gorilla', 'Koko'))
        self.assertIn('Accept', response['Vary'])

    def test_path_scoped_middleware_applies_to_view_requests(self):
        middleware = [*settings.MIDDLEWARE[:-1], f'{__name__}.BlockTemplatePathMiddleware', GLUE_VIEW_MIDDLEWARE_PATH]
        with override_settings(MIDDLEWARE=middleware):
            response = self.client.get(f'/{self.gorilla.pk}/template/', HTTP_ACCEPT=GLUE_VIEW_MEDIA_TYPE)

        self.assertEqual(response.status_code, 403)


class GlueViewMiddlewareCheckTestCase(SimpleTestCase):
    def test_last_middleware_passes(self):
        with override_settings(MIDDLEWARE=['a.Middleware', GLUE_VIEW_MIDDLEWARE_PATH]):
            self.assertEqual(check_glue_view_middleware(), [])

    def test_missing_or_misplaced_middleware_fails_startup(self):
        for middleware in (['a.Middleware'], [GLUE_VIEW_MIDDLEWARE_PATH, 'a.Middleware']):
            with self.subTest(middleware=middleware), override_settings(MIDDLEWARE=middleware):
                self.assertEqual([error.id for error in check_glue_view_middleware()], ['django_glue.E002'])
