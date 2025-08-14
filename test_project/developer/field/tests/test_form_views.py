from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse
from playwright.sync_api import sync_playwright

import os
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")


class BrowserTestCase(StaticLiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._pw = sync_playwright().start()
        cls.browser = cls._pw.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls._pw.stop()
        super().tearDownClass()

    def format_url(self, url: str) -> str:
        return self.live_server_url + url

    def setUp(self):
        self.context = self.browser.new_context()
        self.page = self.context.new_page()

    def tearDown(self):
        self.context.close()


class FieldViewTestCase(BrowserTestCase):
    def setUp(self):
        super().setUp()

    def test_playwright(self):
        # Use the page/context created in setUp
        url = reverse('developer:field:page:input_field')
        self.page.goto(self.format_url(url), wait_until="domcontentloaded")

        self.page.wait_for_selector('#id_input_field')
        self.page.fill('#id_input_field', 'hello work')
        self.assertEqual(self.page.input_value('#id_input_field'), 'hello work')

        submit_button = self.page.get_by_role("button", name="Submit")
        submit_button.click()




