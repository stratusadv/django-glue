"""
Field handling mixin for Django Glue proxies.

Provides field inclusion/exclusion filtering and payload validation
for proxies that work with Django model fields.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Sequence

from django.db.models import ForeignObjectRel
from django.utils.functional import cached_property

from django_glue.exceptions import GluePayloadValidationError
from django_glue.proxies.proxy import BaseGlueProxy
from django_glue.proxies.fields.validators import FIELD_TYPE_VALIDATORS


class GlueProxyFieldsMixin(BaseGlueProxy, ABC):
    """
    Mixin that provides field filtering and validation for model-based proxies.

    This mixin adds the ability to include/exclude specific model fields
    and validates payload data against Django field types before applying
    changes to model instances.

    Attributes:
        fields: Sequence of field names to include. If empty, all fields are included.
        exclude: Sequence of field names to exclude from the proxy.
    """

    def __init__(
        self,
        fields: Sequence = (),
        exclude: Sequence = (),
        **kwargs
    ):
        super().__init__(**kwargs)
        self.fields = fields
        self.exclude = exclude

    @abstractmethod
    def get_model_class(self):
        """Return the Django model class associated with this proxy."""
        raise NotImplementedError("Subclasses must implement get_model_class()")

    def to_session_data(self) -> dict:
        return (
            super().to_session_data() |
            {
                'fields': self.fields,
                'exclude': self.exclude
            } |
            self._build_session_data()
        )

    @cached_property
    def _included_fields(self) -> dict[str, Any]:
        # TODO: we should probably ensure id is in included fields due to how we are
        # queryset instance updates

        deconstructed_fields = [
            field.deconstruct()
            for field in self.get_model_class()._meta.get_fields()
            if (
                    not isinstance(field, ForeignObjectRel) and
                    not field.__class__.__name__ == 'GenericRelation' and
                    not field.name in self.exclude and
                    (not self.fields or field.name in self.fields)
            )
        ]

        return {
            field_name: {
                'type': field_type.rsplit('.', 1)[-1],  # Extract class name from full path
                **{
                    opt_name: opt_value
                    for opt_name, opt_value in field_options.items()
                    if opt_name not in ['default']
                }
            }
            for field_name, field_type, _, field_options in deconstructed_fields
        }

    def _validate_payload_field(
        self,
        field_name: str,
        field_info: dict,
        value: Any
    ) -> Any:
        """
        Validate a single payload field value against its expected type.

        Args:
            field_name: The name of the field being validated.
            field_info: Dictionary containing field metadata including 'type' and 'null'.
            value: The value to validate.

        Returns:
            The validated value (unchanged if valid).

        Raises:
            GluePayloadValidationError: If the value fails type validation.
        """
        field_type = field_info.get('type', '')

        # Allow None for nullable fields
        if value is None:
            if field_info.get('null', False) or field_info.get('blank', False):
                return value
            raise GluePayloadValidationError(
                field=field_name,
                expected_type=field_type,
                received_value=value,
                reason="Field does not allow null values"
            )

        # Get validator for field type
        validator = FIELD_TYPE_VALIDATORS.get(field_type)

        if validator is None:
            # Unknown field type - skip validation (let Django handle it)
            return value

        if not validator(value):
            raise GluePayloadValidationError(
                field=field_name,
                expected_type=field_type,
                received_value=value
            )

        return value

    def _validate_payload(self, payload: dict) -> dict:
        """
        Validate all fields in a payload against the included fields schema.

        Only validates fields that exist in both the payload and _included_fields.
        Fields in the payload that are not in _included_fields are filtered out.

        Args:
            payload: Dictionary of field names to values from the client.

        Returns:
            Dictionary containing only validated fields that exist in _included_fields.

        Raises:
            GluePayloadValidationError: If any field value fails type validation.
        """
        validated = {}

        for field_name, value in payload.items():
            if field_name in self._included_fields:
                validated[field_name] = self._validate_payload_field(
                    field_name,
                    self._included_fields[field_name],
                    value
                )

        return validated
