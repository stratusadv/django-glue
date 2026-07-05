"""
Tests for Django Glue data transfer objects.
"""
import json

from django.test import TestCase, RequestFactory

from django_glue.resolver.action.schemas import ActionRequest


class ActionPayloadSchemaTestCase(TestCase):
    """Tests for ActionPayloadSchema Pydantic model."""

    def test_validates_required_proxy_definition(self):
        """Should require proxy_definition field."""
        data = ActionRequest(proxy_definition={'key': 'value'})

        self.assertEqual(data.proxy_definition, {'key': 'value'})
        self.assertIsNone(data.action_kwargs)
        self.assertIsNone(data.file_data)

    def test_accepts_optional_action_kwargs(self):
        """Should accept optional action_kwargs."""
        data = ActionRequest(
            proxy_definition={},
            action_kwargs={'field': 'value'}
        )

        self.assertEqual(data.action_kwargs, {'field': 'value'})

    def test_accepts_optional_file_data(self):
        """Should accept optional file_data."""
        data = ActionRequest(
            proxy_definition={},
            file_data={'file': 'data'}
        )

        self.assertEqual(data.file_data, {'file': 'data'})


class ActionPayloadSchemaFromRequestJsonTestCase(TestCase):
    """Tests for ActionPayloadSchema.from_request() with JSON."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_parses_json_request(self):
        """Should parse JSON request body correctly."""
        body = {
            'proxy_definition': {'subject_type': 'Model'},
            'action_kwargs': {'name': 'Test'},
            'file_data': {},
        }
        request = self.factory.post(
            '/',
            data=json.dumps(body),
            content_type='application/json'
        )

        data = ActionRequest.from_request(request)

        self.assertEqual(data.proxy_definition, {'subject_type': 'Model'})
        self.assertEqual(data.action_kwargs, {'name': 'Test'})
        self.assertEqual(data.file_data, {})

    def test_handles_json_without_action_kwargs(self):
        """Should handle JSON request without action_kwargs."""
        body = {
            'proxy_definition': {'subject_type': 'Model'},
        }
        request = self.factory.post(
            '/',
            data=json.dumps(body),
            content_type='application/json'
        )

        data = ActionRequest.from_request(request)

        self.assertEqual(data.proxy_definition, {'subject_type': 'Model'})
        self.assertIsNone(data.action_kwargs)


class ActionPayloadSchemaFromRequestMultipartTestCase(TestCase):
    """Tests for ActionPayloadSchema.from_request() with multipart/form-data."""

    def test_parses_multipart_request(self):
        """Should parse multipart/form-data request correctly."""
        from django.test import RequestFactory
        factory = RequestFactory()

        # Build multipart body manually
        boundary = 'BoUnDaRyStRiNg'
        body = (
            f'--{boundary}\r\n'
            f'Content-Disposition: form-data; name="proxy_definition"\r\n\r\n'
            f'{json.dumps({"subject_type": "Model"})}\r\n'
            f'--{boundary}\r\n'
            f'Content-Disposition: form-data; name="name"\r\n\r\n'
            f'Test\r\n'
            f'--{boundary}\r\n'
            f'Content-Disposition: form-data; name="age"\r\n\r\n'
            f'25\r\n'
            f'--{boundary}--\r\n'
        ).encode('utf-8')

        request = factory.post(
            '/',
            data=body,
            content_type=f'multipart/form-data; boundary={boundary}'
        )

        data = ActionRequest.from_request(request)

        self.assertEqual(data.proxy_definition, {'subject_type': 'Model'})
        self.assertEqual(data.action_kwargs, {'name': 'Test', 'age': '25'})

    def test_handles_multiple_values_in_multipart(self):
        """Should handle multiple values for same key in multipart."""
        from django.test import RequestFactory
        factory = RequestFactory()

        boundary = 'BoUnDaRyStRiNg'
        body = (
            f'--{boundary}\r\n'
            f'Content-Disposition: form-data; name="proxy_definition"\r\n\r\n'
            f'{json.dumps({"subject_type": "Model"})}\r\n'
            f'--{boundary}\r\n'
            f'Content-Disposition: form-data; name="tags"\r\n\r\n'
            f'tag1\r\n'
            f'--{boundary}\r\n'
            f'Content-Disposition: form-data; name="tags"\r\n\r\n'
            f'tag2\r\n'
            f'--{boundary}--\r\n'
        ).encode('utf-8')

        request = factory.post(
            '/',
            data=body,
            content_type=f'multipart/form-data; boundary={boundary}'
        )

        data = ActionRequest.from_request(request)

        self.assertEqual(data.action_kwargs['tags'], ['tag1', 'tag2'])

    def test_raises_for_missing_proxy_definition_in_multipart(self):
        """Should raise AttributeError when proxy_definition is missing in multipart."""
        from django.test import RequestFactory
        factory = RequestFactory()

        boundary = 'BoUnDaRyStRiNg'
        body = (
            f'--{boundary}\r\n'
            f'Content-Disposition: form-data; name="name"\r\n\r\n'
            f'Test\r\n'
            f'--{boundary}--\r\n'
        ).encode('utf-8')

        request = factory.post(
            '/',
            data=body,
            content_type=f'multipart/form-data; boundary={boundary}'
        )

        with self.assertRaises(AttributeError):
            ActionRequest.from_request(request)
