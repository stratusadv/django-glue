"""
Tests for Django Glue data transfer objects.
"""
import json

from django.test import TestCase, RequestFactory

from django_glue.resolver.action.schemas import ActionPayloadSchema


class ActionPayloadSchemaTestCase(TestCase):
    """Tests for ActionPayloadSchema Pydantic model."""

    def test_validates_required_context_data(self):
        """Should require context_data field."""
        data = ActionPayloadSchema(context_data={'key': 'value'})

        self.assertEqual(data.context_data, {'key': 'value'})
        self.assertIsNone(data.post_data)
        self.assertIsNone(data.file_data)

    def test_accepts_optional_post_data(self):
        """Should accept optional post_data."""
        data = ActionPayloadSchema(
            context_data={},
            post_data={'field': 'value'}
        )

        self.assertEqual(data.post_data, {'field': 'value'})

    def test_accepts_optional_file_data(self):
        """Should accept optional file_data."""
        data = ActionPayloadSchema(
            context_data={},
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
            'context_data': {'subject_type': 'Model'},
            'post_data': {'name': 'Test'},
            'file_data': {},
        }
        request = self.factory.post(
            '/',
            data=json.dumps(body),
            content_type='application/json'
        )

        data = ActionPayloadSchema.from_request(request)

        self.assertEqual(data.context_data, {'subject_type': 'Model'})
        self.assertEqual(data.post_data, {'name': 'Test'})
        self.assertEqual(data.file_data, {})

    def test_handles_json_without_post_data(self):
        """Should handle JSON request without post_data."""
        body = {
            'context_data': {'subject_type': 'Model'},
        }
        request = self.factory.post(
            '/',
            data=json.dumps(body),
            content_type='application/json'
        )

        data = ActionPayloadSchema.from_request(request)

        self.assertEqual(data.context_data, {'subject_type': 'Model'})
        self.assertIsNone(data.post_data)


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
            f'Content-Disposition: form-data; name="context_data"\r\n\r\n'
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

        data = ActionPayloadSchema.from_request(request)

        self.assertEqual(data.context_data, {'subject_type': 'Model'})
        self.assertEqual(data.post_data, {'name': 'Test', 'age': '25'})

    def test_handles_multiple_values_in_multipart(self):
        """Should handle multiple values for same key in multipart."""
        from django.test import RequestFactory
        factory = RequestFactory()

        boundary = 'BoUnDaRyStRiNg'
        body = (
            f'--{boundary}\r\n'
            f'Content-Disposition: form-data; name="context_data"\r\n\r\n'
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

        data = ActionPayloadSchema.from_request(request)

        self.assertEqual(data.post_data['tags'], ['tag1', 'tag2'])

    def test_raises_for_missing_context_data_in_multipart(self):
        """Should raise AttributeError when context_data is missing in multipart."""
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
            ActionPayloadSchema.from_request(request)
