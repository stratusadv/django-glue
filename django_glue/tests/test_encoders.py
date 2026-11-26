from __future__ import annotations

import datetime
import json
from dataclasses import dataclass
from decimal import Decimal

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from test_project.gorilla.models import Gorilla

from django_glue.encoders import GlueResponseJSONEncoder, _serialize_field_file
from django_glue.glue.attributes.attribute import BoundGlueAttribute
from django_glue.glue.base import BaseGlue
from django_glue.message import GlueMessage
from django_glue.response import GlueResponse


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

    def test_serialize_field_file_does_not_include_path(self):
        """The file's location on the server's disk is not sent to the browser."""
        file = MockFieldFile(path='/var/media/test.txt')

        result = _serialize_field_file(file)

        self.assertNotIn('path', result)

    def test_serialize_field_file_omits_url_on_value_error(self):
        """url raises ValueError when no file is associated."""
        file = MockFieldFile(url=ValueError('No file'))

        result = _serialize_field_file(file)

        self.assertNotIn('url', result)
        self.assertEqual(result['name'], 'test.txt')

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


class GlueResponseJSONEncoderCompositionBoundaryTestCase(TestCase):
    """Raw Django objects are rejected as ordinary value state (composition boundary)."""

    def test_encoder_rejects_raw_model_instance(self):
        gorilla = Gorilla.objects.create(name='Alpha', age=12)

        with self.assertRaisesRegex(TypeError, 'Raw Django object Gorilla'):
            json.dumps(gorilla, cls=GlueResponseJSONEncoder)

    def test_encoder_rejects_raw_queryset(self):
        queryset = Gorilla.objects.all()

        with self.assertRaisesRegex(TypeError, 'Raw Django object QuerySet'):
            json.dumps(queryset, cls=GlueResponseJSONEncoder)

    def test_encoder_rejects_nested_raw_django_object(self):
        gorilla = Gorilla.objects.create(name='Alpha', age=12)

        with self.assertRaisesRegex(TypeError, 'Raw Django object Gorilla'):
            json.dumps(
                {'rows': [{'value': gorilla}]},
                cls=GlueResponseJSONEncoder,
            )


@dataclass(frozen=True)
class _SampleChoice:
    value: str
    label: str
    unit_price: Decimal
    effective_date: datetime.date


@dataclass(frozen=True)
class _NestedPayload:
    title: str
    choices: list[_SampleChoice]


@dataclass(frozen=True)
class _ModelWrapper:
    record: object


@dataclass
class _CyclicNode:
    name: str
    other: _CyclicNode | None = None


class GlueResponseJSONEncoderDataclassTestCase(TestCase):
    """Dataclass serialization preserves Glue's composition boundaries."""

    def test_encoder_serializes_dataclass_with_django_json_types(self):
        choice = _SampleChoice(
            value='consulting',
            label='Consulting',
            unit_price=Decimal('150.00'),
            effective_date=datetime.date(2026, 11, 26),
        )

        result = json.loads(json.dumps(choice, cls=GlueResponseJSONEncoder))

        self.assertEqual(
            result,
            {
                'value': 'consulting',
                'label': 'Consulting',
                'unit_price': '150.00',
                'effective_date': '2026-11-26',
            },
        )

    def test_encoder_serializes_nested_dataclasses(self):
        payload = _NestedPayload(
            title='Products',
            choices=[
                _SampleChoice(
                    value='a',
                    label='A',
                    unit_price=Decimal('10.00'),
                    effective_date=datetime.date(2026, 1, 1),
                ),
            ],
        )

        result = json.loads(json.dumps(payload, cls=GlueResponseJSONEncoder))

        self.assertEqual(result['title'], 'Products')
        self.assertEqual(result['choices'][0]['value'], 'a')

    def test_encoder_rejects_dataclass_type_itself(self):
        with self.assertRaises(TypeError):
            json.dumps(_SampleChoice, cls=GlueResponseJSONEncoder)

    def test_encoder_rejects_raw_django_model_inside_dataclass(self):
        gorilla = Gorilla.objects.create(name='Alpha', age=12)

        with self.assertRaisesRegex(TypeError, 'Raw Django object Gorilla'):
            json.dumps(_ModelWrapper(record=gorilla), cls=GlueResponseJSONEncoder)

    def test_encoder_rejects_raw_queryset_inside_dataclass(self):
        queryset = Gorilla.objects.all()

        with self.assertRaisesRegex(TypeError, 'Raw Django object QuerySet'):
            json.dumps(_ModelWrapper(record=queryset), cls=GlueResponseJSONEncoder)

    def test_encoder_rejects_internal_glue_dataclasses(self):
        with self.assertRaisesRegex(TypeError, 'Internal Glue object GlueResponse'):
            json.dumps(GlueResponse(result='ok'), cls=GlueResponseJSONEncoder)

        with self.assertRaisesRegex(TypeError, 'Internal Glue object GlueMessage'):
            json.dumps(GlueMessage.info('hello'), cls=GlueResponseJSONEncoder)

    def test_encoder_rejects_cyclic_dataclass(self):
        node = _CyclicNode(name='root')
        node.other = node

        with self.assertRaisesRegex(ValueError, 'Circular reference'):
            json.dumps(node, cls=GlueResponseJSONEncoder)

    def test_composition_boundary_rejects_base_glue_inside_dataclass(self):
        class _StubGlue(BaseGlue):
            @classmethod
            def _reconstruct_from_policy(cls, policy, request):
                return None

        stub_glue = object.__new__(_StubGlue)
        wrapped = _ModelWrapper(record=stub_glue)

        with self.assertRaisesRegex(TypeError, r'result\.record'):
            GlueResponse._reject_glue_objects(wrapped)

        self.assertTrue(BoundGlueAttribute._contains_type(wrapped, BaseGlue, set()))
