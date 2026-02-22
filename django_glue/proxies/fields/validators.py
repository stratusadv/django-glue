"""
Field type validators for Django Glue payload validation.

This module contains validation functions for Django model field types
and a mapping dictionary that associates field types with their validators.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Callable


def validate_integer(value: Any) -> bool:
    """Validate that value is or can be an integer."""
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    if isinstance(value, str):
        try:
            int(value)
            return True
        except ValueError:
            return False
    return False


def validate_string(value: Any) -> bool:
    """Validate that value is a string."""
    return isinstance(value, str)


def validate_boolean(value: Any) -> bool:
    """Validate that value is a boolean."""
    return isinstance(value, bool)


def validate_nullable_boolean(value: Any) -> bool:
    """Validate that value is a boolean or None."""
    return value is None or isinstance(value, bool)


def validate_date(value: Any) -> bool:
    """Validate that value is a valid date or ISO date string (YYYY-MM-DD)."""
    if isinstance(value, date) and not isinstance(value, datetime):
        return True
    if isinstance(value, str):
        try:
            datetime.strptime(value, '%Y-%m-%d')
            return True
        except ValueError:
            return False
    return False


def validate_datetime(value: Any) -> bool:
    """Validate that value is a valid datetime or ISO datetime string."""
    if isinstance(value, datetime):
        return True
    if isinstance(value, str):
        try:
            datetime.fromisoformat(value.replace('Z', '+00:00'))
            return True
        except ValueError:
            return False
    return False


def validate_time(value: Any) -> bool:
    """Validate that value is a valid time string (HH:MM:SS)."""
    if isinstance(value, str):
        try:
            datetime.strptime(value, '%H:%M:%S')
            return True
        except ValueError:
            try:
                datetime.strptime(value, '%H:%M:%S.%f')
                return True
            except ValueError:
                return False
    return False


def validate_decimal(value: Any) -> bool:
    """Validate that value can be converted to Decimal."""
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float, Decimal)):
        return True
    if isinstance(value, str):
        try:
            Decimal(value)
            return True
        except InvalidOperation:
            return False
    return False


def validate_float(value: Any) -> bool:
    """Validate that value is a numeric type (int or float, not bool)."""
    if isinstance(value, bool):
        return False
    return isinstance(value, (int, float))


def validate_foreign_key(value: Any) -> bool:
    """Validate that value is a valid foreign key (int, string, or None)."""
    return value is None or isinstance(value, (int, str))


def validate_json(value: Any) -> bool:
    """Validate JSON field - any JSON-serializable value is valid."""
    return True


FIELD_TYPE_VALIDATORS: dict[str, Callable[[Any], bool]] = {
    # Auto fields
    'AutoField': validate_integer,
    'BigAutoField': validate_integer,
    'SmallAutoField': validate_integer,

    # Integer fields
    'IntegerField': validate_integer,
    'SmallIntegerField': validate_integer,
    'BigIntegerField': validate_integer,
    'PositiveIntegerField': validate_integer,
    'PositiveSmallIntegerField': validate_integer,
    'PositiveBigIntegerField': validate_integer,

    # String fields
    'CharField': validate_string,
    'TextField': validate_string,
    'EmailField': validate_string,
    'URLField': validate_string,
    'SlugField': validate_string,
    'UUIDField': validate_string,
    'IPAddressField': validate_string,
    'GenericIPAddressField': validate_string,
    'FilePathField': validate_string,

    # Boolean fields
    'BooleanField': validate_boolean,
    'NullBooleanField': validate_nullable_boolean,

    # Date/time fields
    'DateField': validate_date,
    'DateTimeField': validate_datetime,
    'TimeField': validate_time,

    # Numeric fields
    'DecimalField': validate_decimal,
    'FloatField': validate_float,

    # Relation fields
    'ForeignKey': validate_foreign_key,
    'OneToOneField': validate_foreign_key,

    # JSON field
    'JSONField': validate_json,
}
