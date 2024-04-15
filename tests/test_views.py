from django.test import TestCase
from django.urls import reverse, get_resolver


class TestViews(TestCase):
    def test_model_object_view(self):
        print(get_resolver().reverse_dict.keys())
        response = self.client.get(reverse('model_object'))
        self.assertTrue(response.status_code == 200)

    def test_function_view(self):
        print(get_resolver().reverse_dict.keys())
        response = self.client.get(reverse('function'))
        self.assertTrue(response.status_code == 200)

    def test_template_view(self):
        print(get_resolver().reverse_dict.keys())
        response = self.client.get(reverse('template'))
        self.assertTrue(response.status_code == 200)

    def test_view_view(self):
        print(get_resolver().reverse_dict.keys())
        response = self.client.get(reverse('view'))
        self.assertTrue(response.status_code == 200)