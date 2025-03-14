from django.test import TestCase
from django.urls import reverse

class EngineeringReportViewTestCase(TestCase):
    def setUp(self):
        super().setUp()

    def test_home_url_path(self):
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)