from __future__ import annotations

import json

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from django_glue.encoders import GlueResponseJSONEncoder, _serialize_field_file


class MockFieldFile:
    def __init__(
        self,
        *,
        name='test.txt',
        url='/media/test.txt',
        path='/var/media/test.txt',
    ):
        self.name = name
        self._url = url
        self._path = path

    def __bool__(self):
        return True

    @property
    def url(self):
        if isinstance(self._url, Exception):
            raise self._url
        return self._url

    @property
    def path(self):
        if isinstance(self._path, Exception):
            raise self._path
        return self._path


class SerializeFileTestCase(TestCase):
    """Tests for the _serialize_field_file helper function."""

    def test_serialize_field_file_includes_name(self):
        file = MockFieldFile(name='test.txt')

        result = _serialize_field_file(file)

        self.assertEqual(result['name'], 'test.txt')

    def test_serialize_field_file_includes_url_when_available(self):
        file = MockFieldFile(url='/media/test.txt')

        result = _serialize_field_file(file)

        self.assertEqual(result['url'], '/media/test.txt')

    def test_serialize_field_file_includes_path_when_available(self):
        file = MockFieldFile(path='/var/media/test.txt')

        result = _serialize_field_file(file)

        self.assertEqual(result['path'], '/var/media/test.txt')

    def test_serialize_field_file_omits_url_on_value_error(self):
        """url raises ValueError when no file is associated."""
        file = MockFieldFile(url=ValueError('No file'))

        result = _serialize_field_file(file)

        self.assertNotIn('url', result)
        self.assertEqual(result['name'], 'test.txt')

    def test_serialize_field_file_omits_path_on_not_implemented_error(self):
        """path raises NotImplementedError for remote storage backends."""
        file = MockFieldFile(
            url='https://s3.example.com/test.txt',
            path=NotImplementedError(),
        )

        result = _serialize_field_file(file)

        self.assertNotIn('path', result)
        self.assertEqual(result['name'], 'test.txt')
        self.assertEqual(result['url'], 'https://s3.example.com/test.txt')

    def test_serialize_field_file_does_not_include_size(self):
        """Size is intentionally omitted for performance with remote storage."""
        file = MockFieldFile()
        file.size = 1234

        result = _serialize_field_file(file)

        self.assertNotIn('size', result)


class GlueResponseJSONEncoderFileTestCase(TestCase):
    """Tests for File serialization via GlueResponseJSONEncoder."""

    def test_encoder_serializes_uploaded_file(self):
        uploaded = SimpleUploadedFile('upload.txt', b'content')

        result = json.loads(json.dumps(uploaded, cls=GlueResponseJSONEncoder))

        self.assertEqual(result['name'], 'upload.txt')
        self.assertNotIn('size', result)

    def test_encoder_serializes_content_file(self):
        content_file = ContentFile(b'content', name='content.txt')

        result = json.loads(json.dumps(content_file, cls=GlueResponseJSONEncoder))

        self.assertEqual(result['name'], 'content.txt')
