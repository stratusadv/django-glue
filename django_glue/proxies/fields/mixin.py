"""
Field handling mixin for Django Glue model proxies.

Provides field inclusion/exclusion filtering and payload validation
for proxies that work with Django model fields.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Sequence

from django.db.models import ForeignObjectRel
from django.forms import modelform_factory
from django.utils.functional import cached_property

from django_glue.exceptions import GluePayloadValidationError
from django_glue.proxies.proxy import BaseGlueProxy


class GlueProxyModelFieldsMixin(BaseGlueProxy, ABC):
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

        # Options to exclude from field metadata (not JSON serializable or not needed)
        excluded_options = {'default', 'validators', 'on_delete'}

        return {
            field_name: {
                'type': field_type.rsplit('.', 1)[-1],  # Extract class name from full path
                **{
                    opt_name: opt_value
                    for opt_name, opt_value in field_options.items()
                    if opt_name not in excluded_options
                }
            }
            for field_name, field_type, _, field_options in deconstructed_fields
        }

    def _validate_payload(self, payload: dict) -> dict:
        # Filter payload to only include allowed fields
        filtered_payload = {
            field_name: value
            for field_name, value in payload.items()
            if field_name in self._included_fields
        }

        if not filtered_payload:
            return {}

        # Get fields that are in the payload and included
        fields_to_validate = list(filtered_payload.keys())

        # Create a dynamic ModelForm for validation
        DynamicForm = modelform_factory(
            self.get_model_class(),
            fields=fields_to_validate
        )

        # Validate using the form
        form = DynamicForm(data=filtered_payload)

        if not form.is_valid():
            # Raise validation error with first field error
            for field_name, errors in form.errors.items():
                field_info = self._included_fields.get(field_name, {})
                raise GluePayloadValidationError(
                    field=field_name,
                    expected_type=field_info.get('type', 'unknown'),
                    received_value=filtered_payload.get(field_name),
                    reason=errors[0]
                )

        return form.cleaned_data
