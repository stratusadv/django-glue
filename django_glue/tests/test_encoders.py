from __future__ import annotations

import json
from unittest.mock import Mock, PropertyMock

from django.core.files.base import ContentFile, File
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from django_glue.encoders import GlueResponseJSONEncoder, _serialize_file


class SerializeFileTestCase(TestCase):
    """Tests for the _serialize_file helper function."""

    def test_serialize_file_includes_name(self):
        file = Mock(spec=File)
        file.name = 'test.txt'

        result = _serialize_file(file)

        self.assertEqual(result['name'], 'test.txt')

    def test_serialize_file_includes_url_when_available(self):
        file = Mock(spec=File)
        file.name = 'test.txt'
        file.url = '/media/test.txt'

        result = _serialize_file(file)

        self.assertEqual(result['url'], '/media/test.txt')

    def test_serialize_file_includes_path_when_available(self):
        file = Mock(spec=File)
        file.name = 'test.txt'
        file.path = '/var/media/test.txt'

        result = _serialize_file(file)

        self.assertEqual(result['path'], '/var/media/test.txt')

    def test_serialize_file_omits_url_on_value_error(self):
        """url raises ValueError when no file is associated."""
        file = Mock(spec=File)
        file.name = 'test.txt'
        type(file).url = PropertyMock(side_effect=ValueError('No file'))

        result = _serialize_file(file)

        self.assertNotIn('url', result)
        self.assertEqual(result['name'], 'test.txt')

    def test_serialize_file_omits_path_on_not_implemented_error(self):
        """path raises NotImplementedError for remote storage backends."""
        file = Mock(spec=File)
        file.name = 'test.txt'
        file.url = 'https://s3.example.com/test.txt'
        type(file).path = PropertyMock(side_effect=NotImplementedError())

        result = _serialize_file(file)

        self.assertNotIn('path', result)
        self.assertEqual(result['name'], 'test.txt')
        self.assertEqual(result['url'], 'https://s3.example.com/test.txt')

    def test_serialize_file_does_not_include_size(self):
        """Size is intentionally omitted for performance with remote storage."""
        file = Mock(spec=File)
        file.name = 'test.txt'
        file.size = 1234

        result = _serialize_file(file)

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
