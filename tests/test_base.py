from importlib import import_module

from django.conf import settings
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import TestCase, RequestFactory
from example.app.people.models import Person


class BaseTestCase(TestCase):
    def setUp(self) -> None:
        self.person_model_object = Person(first_name='John', last_name='Doe', age=30)
        self.person_model_class = Person

        self.request_factory = RequestFactory()
        self.request = self.request_factory.get('/fake_url/for_people/')
        self.request.session = import_module(settings.SESSION_ENGINE).SessionStore()
