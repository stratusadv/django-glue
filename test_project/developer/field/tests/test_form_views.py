from django.contrib.staticfiles.testing import StaticLiveServerTestCase
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
        self.page.goto("https://example.com", wait_until="domcontentloaded", timeout=5000)
        print(self.page.title())

    def test_playwright2(self):
        self.page.goto("https://example.com", wait_until="domcontentloaded", timeout=5000)
        print(self.page.title())


