import json
import os
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_project.settings')
django.setup()

from django.test import TestCase
from django_glue.resolver.attribute_event.encoders import BoundAttributeDataJSONEncoder


class BoundAttributeDataJSONEncoderTestCase(TestCase):
    """Tests for BoundAttributeDataJSONEncoder."""

    def test_encodes_memoryview_as_string(self):
        """Test that memoryview objects (from PostgreSQL BinaryField) are decoded to string."""
        binary_data = b'Hello, World!'
        memoryview_obj = memoryview(binary_data)

        result = json.dumps({'data': memoryview_obj}, cls=BoundAttributeDataJSONEncoder)
        parsed = json.loads(result)

        self.assertEqual(parsed['data'], 'Hello, World!')

    def test_encodes_memoryview_with_invalid_utf8_uses_replacement(self):
        """Test that memoryview with invalid UTF-8 bytes uses replacement character."""
        binary_data = b'Hello \xff\xfe World'
        memoryview_obj = memoryview(binary_data)

        result = json.dumps({'data': memoryview_obj}, cls=BoundAttributeDataJSONEncoder)
        parsed = json.loads(result)

        self.assertIn('Hello', parsed['data'])
        self.assertIn('World', parsed['data'])

    def test_encodes_bytes_as_string(self):
        """Test that bytes objects are decoded to string."""
        binary_data = b'Hello, World!'

        result = json.dumps({'data': binary_data}, cls=BoundAttributeDataJSONEncoder)
        parsed = json.loads(result)

        self.assertEqual(parsed['data'], 'Hello, World!')

    def test_encodes_bytes_with_invalid_utf8_uses_replacement(self):
        """Test that bytes with invalid UTF-8 uses replacement character."""
        binary_data = b'Hello \xff\xfe World'

        result = json.dumps({'data': binary_data}, cls=BoundAttributeDataJSONEncoder)
        parsed = json.loads(result)

        self.assertIn('Hello', parsed['data'])
        self.assertIn('World', parsed['data'])

    def test_encodes_regular_dict_without_memoryview(self):
        """Test that regular dicts still encode correctly."""
        data = {'name': 'Kong', 'wins': 10}

        result = json.dumps(data, cls=BoundAttributeDataJSONEncoder)
        parsed = json.loads(result)

        self.assertEqual(parsed, data)

    def test_encodes_datetime_via_django_encoder(self):
        """Test that datetime objects are handled by the parent DjangoJSONEncoder."""
        dt = datetime(2024, 1, 15, 10, 30, 0)
        data = {'created_at': dt}

        result = json.dumps(data, cls=BoundAttributeDataJSONEncoder)
        parsed = json.loads(result)

        self.assertEqual(parsed['created_at'], '2024-01-15T10:30:00')

    def test_encodes_date_via_django_encoder(self):
        """Test that date objects are handled by the parent DjangoJSONEncoder."""
        d = date(2024, 1, 15)
        data = {'birth_date': d}

        result = json.dumps(data, cls=BoundAttributeDataJSONEncoder)
        parsed = json.loads(result)

        self.assertEqual(parsed['birth_date'], '2024-01-15')

    def test_encodes_decimal_via_django_encoder(self):
        """Test that Decimal objects are handled by the parent DjangoJSONEncoder."""
        data = {'price': Decimal('19.99')}

        result = json.dumps(data, cls=BoundAttributeDataJSONEncoder)
        parsed = json.loads(result)

        self.assertEqual(parsed['price'], '19.99')

    def test_encodes_uuid_via_django_encoder(self):
        """Test that UUID objects are handled by the parent DjangoJSONEncoder."""
        uuid = UUID('12345678-1234-5678-1234-567812345678')
        data = {'id': uuid}

        result = json.dumps(data, cls=BoundAttributeDataJSONEncoder)
        parsed = json.loads(result)

        self.assertEqual(parsed['id'], '12345678-1234-5678-1234-567812345678')
