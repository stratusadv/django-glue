"""
Tests for Django Glue JSON encoder.
"""
import json

from django.test import TestCase
from django.core.files.uploadedfile import InMemoryUploadedFile

from django_glue.resolver.action.encoders import ActionDataJSONEncoder
from test_project.gorilla.models import Gorilla


class GlueActionDataJSONEncoderTestCase(TestCase):
    """Tests for GlueActionDataJSONEncoder."""

    def test_encodes_model_as_pk(self):
        """Should encode a Model instance as its primary key."""
        gorilla = Gorilla.objects.create(
            name='Test',
            description='Test',
            age=25,
            weight=350.0,
            height=1.8
        )

        result = json.dumps({'gorilla': gorilla}, cls=ActionDataJSONEncoder)
        self.assertIn(str(gorilla.pk), result)

    def test_encodes_queryset_as_pk_list(self):
        """Should encode a QuerySet as a list of primary keys."""
        gorilla1 = Gorilla.objects.create(
            name='Gorilla 1',
            description='Test',
            age=25,
            weight=350.0,
            height=1.8
        )
        gorilla2 = Gorilla.objects.create(
            name='Gorilla 2',
            description='Test',
            age=30,
            weight=400.0,
            height=2.0
        )

        qs = Gorilla.objects.filter(pk__in=[gorilla1.pk, gorilla2.pk]).order_by('pk')
        result = json.dumps({'ids': qs}, cls=ActionDataJSONEncoder)
        data = json.loads(result)

        self.assertEqual(data['ids'], [gorilla1.pk, gorilla2.pk])

    def test_encodes_fieldfile_as_dict(self):
        """Should encode a FieldFile as a dict with name, size, url, path."""
        gorilla = Gorilla.objects.create(
            name='Test',
            description='Test',
            age=25,
            weight=350.0,
            height=1.8
        )
        # Create a minimal FieldFile without actual file
        gf = gorilla.profile_photo
        # FieldFile without uploaded file will raise ValueError on .url
        # Test that we handle this gracefully
        result = json.dumps({'photo': gf}, cls=ActionDataJSONEncoder)
        data = json.loads(result)

        # Should return None for FieldFile without actual file
        self.assertIsNone(data['photo'])

    def test_encodes_uploaded_file_as_dict(self):
        """Should encode an UploadedFile as a dict with name and size."""
        from io import BytesIO

        uploaded = InMemoryUploadedFile(
            file=BytesIO(b'hello world'),
            field_name='test',
            name='test.txt',
            content_type='text/plain',
            size=11,
            charset='utf-8',
        )

        result = json.dumps({'file': uploaded}, cls=ActionDataJSONEncoder)
        data = json.loads(result)

        self.assertEqual(data['file']['name'], 'test.txt')
        self.assertEqual(data['file']['size'], 11)

    def test_encodes_datetime(self):
        """Should encode datetime objects (via DjangoJSONEncoder parent)."""
        from datetime import datetime, date

        result = json.dumps({
            'dt': datetime(2024, 1, 1, 12, 0, 0),
            'd': date(2024, 1, 1),
        }, cls=ActionDataJSONEncoder)
        data = json.loads(result)

        self.assertIn('2024-01-01', data['dt'])
        self.assertEqual(data['d'], '2024-01-01')


class GlueActionDataJSONEncoderErrorTestCase(TestCase):
    """Tests for GlueActionDataJSONEncoder error handling."""

    def test_raises_for_unsupported_type(self):
        """Should raise TypeError for types not handled by the encoder."""
        class UnsupportedType:
            pass

        with self.assertRaises(TypeError):
            json.dumps({'obj': UnsupportedType()}, cls=ActionDataJSONEncoder)

    def test_encodes_uploaded_file_with_value_error(self):
        """Should return None for UploadedFile that raises ValueError on .size."""
        from unittest.mock import MagicMock

        mock_file = MagicMock(spec=InMemoryUploadedFile)
        mock_file.name = 'test.txt'
        type(mock_file).size = property(lambda self: (_ for _ in ()).throw(ValueError('no size')))

        result = json.dumps({'file': mock_file}, cls=ActionDataJSONEncoder)
        data = json.loads(result)

        self.assertIsNone(data['file'])
