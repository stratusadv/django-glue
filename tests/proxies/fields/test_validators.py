"""
Tests for Django Glue field validators.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_project.base_settings')
django.setup()

from datetime import date, datetime
from decimal import Decimal
from django.test import TestCase

from django_glue.proxies.fields.validators import (
    validate_integer,
    validate_string,
    validate_boolean,
    validate_nullable_boolean,
    validate_date,
    validate_datetime,
    validate_time,
    validate_decimal,
    validate_float,
    validate_foreign_key,
    validate_json,
    FIELD_TYPE_VALIDATORS,
)


class ValidateIntegerTestCase(TestCase):
    """Tests for validate_integer function."""

    def test_accepts_integer(self):
        self.assertTrue(validate_integer(42))

    def test_accepts_negative_integer(self):
        self.assertTrue(validate_integer(-10))

    def test_accepts_zero(self):
        self.assertTrue(validate_integer(0))

    def test_accepts_string_integer(self):
        self.assertTrue(validate_integer('123'))

    def test_accepts_negative_string_integer(self):
        self.assertTrue(validate_integer('-456'))

    def test_rejects_boolean_true(self):
        """Booleans should not be accepted as integers."""
        self.assertFalse(validate_integer(True))

    def test_rejects_boolean_false(self):
        self.assertFalse(validate_integer(False))

    def test_rejects_float(self):
        self.assertFalse(validate_integer(3.14))

    def test_rejects_non_numeric_string(self):
        self.assertFalse(validate_integer('abc'))

    def test_rejects_none(self):
        self.assertFalse(validate_integer(None))


class ValidateStringTestCase(TestCase):
    """Tests for validate_string function."""

    def test_accepts_string(self):
        self.assertTrue(validate_string('hello'))

    def test_accepts_empty_string(self):
        self.assertTrue(validate_string(''))

    def test_rejects_integer(self):
        self.assertFalse(validate_string(42))

    def test_rejects_none(self):
        self.assertFalse(validate_string(None))


class ValidateBooleanTestCase(TestCase):
    """Tests for validate_boolean function."""

    def test_accepts_true(self):
        self.assertTrue(validate_boolean(True))

    def test_accepts_false(self):
        self.assertTrue(validate_boolean(False))

    def test_rejects_integer_one(self):
        self.assertFalse(validate_boolean(1))

    def test_rejects_integer_zero(self):
        self.assertFalse(validate_boolean(0))

    def test_rejects_string(self):
        self.assertFalse(validate_boolean('true'))

    def test_rejects_none(self):
        self.assertFalse(validate_boolean(None))


class ValidateNullableBooleanTestCase(TestCase):
    """Tests for validate_nullable_boolean function."""

    def test_accepts_true(self):
        self.assertTrue(validate_nullable_boolean(True))

    def test_accepts_false(self):
        self.assertTrue(validate_nullable_boolean(False))

    def test_accepts_none(self):
        self.assertTrue(validate_nullable_boolean(None))

    def test_rejects_integer(self):
        self.assertFalse(validate_nullable_boolean(1))


class ValidateDateTestCase(TestCase):
    """Tests for validate_date function."""

    def test_accepts_date_object(self):
        self.assertTrue(validate_date(date(2024, 1, 15)))

    def test_accepts_iso_date_string(self):
        self.assertTrue(validate_date('2024-01-15'))

    def test_rejects_datetime_object(self):
        """datetime should not be accepted as date."""
        self.assertFalse(validate_date(datetime(2024, 1, 15, 10, 30)))

    def test_rejects_invalid_date_string(self):
        self.assertFalse(validate_date('15-01-2024'))

    def test_rejects_datetime_string(self):
        self.assertFalse(validate_date('2024-01-15T10:30:00'))

    def test_rejects_none(self):
        self.assertFalse(validate_date(None))


class ValidateDateTimeTestCase(TestCase):
    """Tests for validate_datetime function."""

    def test_accepts_datetime_object(self):
        self.assertTrue(validate_datetime(datetime(2024, 1, 15, 10, 30)))

    def test_accepts_iso_datetime_string(self):
        self.assertTrue(validate_datetime('2024-01-15T10:30:00'))

    def test_accepts_datetime_with_microseconds(self):
        self.assertTrue(validate_datetime('2024-01-15T10:30:00.123456'))

    def test_accepts_datetime_with_z_suffix(self):
        self.assertTrue(validate_datetime('2024-01-15T10:30:00Z'))

    def test_accepts_datetime_with_timezone(self):
        self.assertTrue(validate_datetime('2024-01-15T10:30:00+00:00'))

    def test_rejects_invalid_string(self):
        self.assertFalse(validate_datetime('not a datetime'))

    def test_rejects_none(self):
        self.assertFalse(validate_datetime(None))


class ValidateTimeTestCase(TestCase):
    """Tests for validate_time function."""

    def test_accepts_time_string(self):
        self.assertTrue(validate_time('10:30:00'))

    def test_accepts_time_with_microseconds(self):
        self.assertTrue(validate_time('10:30:00.123456'))

    def test_rejects_invalid_time(self):
        self.assertFalse(validate_time('25:00:00'))

    def test_rejects_partial_time(self):
        self.assertFalse(validate_time('10:30'))

    def test_rejects_none(self):
        self.assertFalse(validate_time(None))


class ValidateDecimalTestCase(TestCase):
    """Tests for validate_decimal function."""

    def test_accepts_decimal(self):
        self.assertTrue(validate_decimal(Decimal('10.50')))

    def test_accepts_integer(self):
        self.assertTrue(validate_decimal(42))

    def test_accepts_float(self):
        self.assertTrue(validate_decimal(3.14))

    def test_accepts_string_decimal(self):
        self.assertTrue(validate_decimal('99.99'))

    def test_rejects_boolean(self):
        self.assertFalse(validate_decimal(True))

    def test_rejects_invalid_string(self):
        self.assertFalse(validate_decimal('not a number'))

    def test_rejects_none(self):
        self.assertFalse(validate_decimal(None))


class ValidateFloatTestCase(TestCase):
    """Tests for validate_float function."""

    def test_accepts_float(self):
        self.assertTrue(validate_float(3.14))

    def test_accepts_integer(self):
        self.assertTrue(validate_float(42))

    def test_rejects_boolean(self):
        self.assertFalse(validate_float(True))

    def test_rejects_string(self):
        self.assertFalse(validate_float('3.14'))

    def test_rejects_none(self):
        self.assertFalse(validate_float(None))


class ValidateForeignKeyTestCase(TestCase):
    """Tests for validate_foreign_key function."""

    def test_accepts_integer(self):
        self.assertTrue(validate_foreign_key(1))

    def test_accepts_string(self):
        self.assertTrue(validate_foreign_key('uuid-string'))

    def test_accepts_none(self):
        self.assertTrue(validate_foreign_key(None))

    def test_rejects_list(self):
        self.assertFalse(validate_foreign_key([1, 2, 3]))


class ValidateJsonTestCase(TestCase):
    """Tests for validate_json function."""

    def test_accepts_dict(self):
        self.assertTrue(validate_json({'key': 'value'}))

    def test_accepts_list(self):
        self.assertTrue(validate_json([1, 2, 3]))

    def test_accepts_string(self):
        self.assertTrue(validate_json('string'))

    def test_accepts_none(self):
        self.assertTrue(validate_json(None))


class FieldTypeValidatorsMapTestCase(TestCase):
    """Tests for FIELD_TYPE_VALIDATORS mapping."""

    def test_integer_fields_use_integer_validator(self):
        integer_fields = [
            'AutoField', 'BigAutoField', 'SmallAutoField',
            'IntegerField', 'SmallIntegerField', 'BigIntegerField',
            'PositiveIntegerField', 'PositiveSmallIntegerField', 'PositiveBigIntegerField'
        ]
        for field_type in integer_fields:
            self.assertEqual(
                FIELD_TYPE_VALIDATORS[field_type],
                validate_integer,
                f"{field_type} should use validate_integer"
            )

    def test_string_fields_use_string_validator(self):
        string_fields = [
            'CharField', 'TextField', 'EmailField', 'URLField',
            'SlugField', 'UUIDField', 'IPAddressField', 'GenericIPAddressField',
            'FilePathField'
        ]
        for field_type in string_fields:
            self.assertEqual(
                FIELD_TYPE_VALIDATORS[field_type],
                validate_string,
                f"{field_type} should use validate_string"
            )

    def test_boolean_field_uses_boolean_validator(self):
        self.assertEqual(FIELD_TYPE_VALIDATORS['BooleanField'], validate_boolean)

    def test_date_field_uses_date_validator(self):
        self.assertEqual(FIELD_TYPE_VALIDATORS['DateField'], validate_date)

    def test_datetime_field_uses_datetime_validator(self):
        self.assertEqual(FIELD_TYPE_VALIDATORS['DateTimeField'], validate_datetime)

    def test_decimal_field_uses_decimal_validator(self):
        self.assertEqual(FIELD_TYPE_VALIDATORS['DecimalField'], validate_decimal)

    def test_float_field_uses_float_validator(self):
        self.assertEqual(FIELD_TYPE_VALIDATORS['FloatField'], validate_float)

    def test_foreign_key_uses_foreign_key_validator(self):
        self.assertEqual(FIELD_TYPE_VALIDATORS['ForeignKey'], validate_foreign_key)

    def test_json_field_uses_json_validator(self):
        self.assertEqual(FIELD_TYPE_VALIDATORS['JSONField'], validate_json)
