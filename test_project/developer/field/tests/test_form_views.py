from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse
from playwright.sync_api import sync_playwright

# import os
# os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")
#
#
# class BrowserTestCase(StaticLiveServerTestCase):
#     @classmethod
#     def setUpClass(cls):
#         super().setUpClass()
#         cls._pw = sync_playwright().start()
#         cls.browser = cls._pw.chromium.launch(headless=True)
#
#     @classmethod
#     def tearDownClass(cls):
#         cls.browser.close()
#         cls._pw.stop()
#         super().tearDownClass()
#
#     def format_url(self, url: str) -> str:
#         return self.live_server_url + url
#
#     def setUp(self):
#         self.context = self.browser.new_context()
#         self.page = self.context.new_page()
#
#     def tearDown(self):
#         self.context.close()
#
#
# class FieldViewTestCase(BrowserTestCase):
#     def setUp(self):
#         super().setUp()
#
#     def test_playwright_ajax_endpoint_validation(self):
#         # Use the page/context created in setUp
#         url = reverse('developer:field:page:input_field')
#         self.page.goto(self.format_url(url), wait_until="domcontentloaded")
#
#         self.page.wait_for_selector('#id_input_field')
#         self.page.fill('#id_input_field', 'hello work')
#         self.assertEqual(self.page.input_value('#id_input_field'), 'hello work')
#
#         ajax_url = reverse('developer:field:page:endpoint_testing')
#
#         # Define what “the save call” looks like:
#         def is_save(resp):
#             return resp.url.endswith(ajax_url) and resp.request.method == "POST"
#
#         # Arm the waiter BEFORE clicking
#         with self.page.expect_response(is_save) as resp_info:
#             self.page.get_by_role("button", name="Submit").click()
#
#         response = resp_info.value
#         self.assertEqual(response.status, 200)
#
#         # Inspect the request that produced this response
#         req = response.request
#         payload = req.post_data_json
#         print(payload)
#
#
#     def test_post_form_body_is_correct(self):
#         from django.http import QueryDict
#         path = reverse('developer:field:page:input_field')   # your form action path
#         target_url_prefix = self.live_server_url + path
#
#         seen = {}  # will store what the browser sent
#
#         def spy(route, request):
#             # catch the navigation POST to your action URL
#             if request.method == "POST" and request.url.startswith(target_url_prefix):
#                 seen["headers"] = request.headers
#                 seen["json"] = request.post_data_json
#                 seen["raw"] = request.post_data or ""
#                 # convert into django querydict for actual django data!
#                 q = QueryDict(request.post_data_buffer, encoding="utf-8")
#                 print('In spy!!')
#                 print(q)
#                 print(request.post_data_json)
#             route.continue_()
#
#         # Attach the spy BEFORE interacting
#         self.context.route("**/*", spy)
#
#         # Go fill and submit
#         form_page = self.live_server_url + reverse("developer:field:page:input_field")
#         self.page.goto(form_page, wait_until="domcontentloaded")
#         self.page.fill("#id_input_field", "hello work")
#
#         with self.page.expect_navigation():
#             self.page.get_by_role("button", name="Submit").click()
#
#         # Assert the payload
#         # if seen.get("json") is not None:
#         #     self.assertEqual(seen["json"]["input_field"], "hello work")
#         # else:
#         #     params = parse_qs(seen.get("raw") or "")
#         #     self.assertEqual(params.get("input_field", [""])[0], "hello work")