from importlib import import_module

from django.conf import settings
from django.test import TestCase, RequestFactory

from test_project.app.gorilla.models import Gorilla


class BaseTestCase(TestCase):
    def setUp(self) -> None:
        self.gorilla_model_object = Gorilla(name='John')
        self.gorilla_model_class = Gorilla

        self.request_factory = RequestFactory()
        self.request = self.request_factory.get('/fake_url/for_people/')
        self.request.session = import_module(settings.SESSION_ENGINE).SessionStore()
