import json
import os
from datetime import timedelta
from unittest.mock import patch

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_project.settings')
django.setup()

from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone
from pydantic import ValidationError

from django_glue.constants import DJANGO_GLUE_PROXIES_REQUEST_ATTR_KEY
from django_glue.exceptions import GlueExpiredPolicyError
from django_glue.resolver.attribute_event.schemas import BoundProxyAttributeEvent
from django_glue.tests.proxies.queryset.helpers import make_queryset_proxy
from test_project.gorilla.models import Gorilla


class BoundProxyAttributeEventSchemaTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.gorilla = Gorilla.objects.create(
            name='Test Gorilla',
            description='Test',
            age=18,
            weight=200.0,
            height=1.8,
        )

    def _queryset_policy(self):
        registration_request = self.factory.get('/')
        proxy = make_queryset_proxy(Gorilla.objects.all())
        proxy._register_with_request(registration_request)
        return registration_request.__dict__[DJANGO_GLUE_PROXIES_REQUEST_ATTR_KEY]['gorillas']['policy']

    def _event_request(self, policy, *, proxy_name='gorillas', attribute_name='GlueQuerySetProxy.new'):
        request = self.factory.post(
            f'/__dg__/bound_attribute_event/{proxy_name}/{attribute_name}/',
            data={'policy': json.dumps(policy)},
        )
        request.resolver_match = type(
            'ResolverMatch',
            (),
            {'kwargs': {'proxy_name': proxy_name, 'attribute_name': attribute_name}},
        )()
        return request

    def test_validates_bound_attribute_event_request(self):
        request = self._event_request(self._queryset_policy())

        event = BoundProxyAttributeEvent.model_validate(request)

        self.assertEqual(event.policy.name, 'gorillas')
        self.assertEqual(event.bound_attribute.name, 'new')

    def test_missing_bound_attribute_raises_pydantic_validation_error(self):
        request = self._event_request(self._queryset_policy(), attribute_name='new')

        with self.assertRaises(ValidationError) as cm:
            BoundProxyAttributeEvent.model_validate(request)

        self.assertIn(
            'Bound attribute for event was not included in policy: new',
            str(cm.exception),
        )

    def test_proxy_name_mismatch_raises_pydantic_validation_error(self):
        request = self._event_request(self._queryset_policy(), proxy_name='wrong')

        with self.assertRaises(ValidationError) as cm:
            BoundProxyAttributeEvent.model_validate(request)

        self.assertIn('Proxy name mismatch between URL path and policy', str(cm.exception))

    @override_settings(DJANGO_GLUE_PROXY_POLICY_MAX_AGE_SECONDS=60)
    def test_expired_policy_raises_expired_policy_error(self):
        stale_now = timezone.now() - timedelta(seconds=61)
        with patch('django_glue.proxies.policy.timezone.now', return_value=stale_now):
            policy = self._queryset_policy()

        request = self._event_request(policy)

        with self.assertRaises(GlueExpiredPolicyError):
            BoundProxyAttributeEvent.model_validate(request)
