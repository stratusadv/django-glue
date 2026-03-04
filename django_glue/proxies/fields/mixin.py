"""
Field handling mixin for Django Glue model proxies.

Provides field inclusion/exclusion filtering and payload validation
for proxies that work with Django model fields.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Sequence, TYPE_CHECKING

from django.db.models import ForeignObjectRel, QuerySet
from django.forms import modelform_factory, ModelChoiceField
from django.forms.forms import BaseForm
from django.forms.models import ModelForm
from django.utils.functional import cached_property

from django_glue.exceptions import GluePayloadValidationError
from django_glue.proxies.proxy import BaseGlueProxy
from django_glue.utils import get_class_from_path_string, serialize_queryset, deserialize_queryset

if TYPE_CHECKING:
    from django_glue.shortcuts import ForeignKeyField


class GlueProxyModelFieldsMixin(BaseGlueProxy, ABC):
    """
    Mixin that provides field filtering and validation for model-based proxies.

    This mixin adds the ability to include/exclude specific model fields
    and validates payload data against Django field types before applying
    changes to model instances.

    Attributes:
        fields: Sequence of field names to include. If empty, all fields are included.
        exclude: Sequence of field names to exclude from the proxy.
        field_overrides: Dict mapping field names to custom QuerySets for ForeignKey validation.
    """

    def __init__(
        self,
        fields: Sequence = (),
        exclude: Sequence[str] = (),
        form_class: type[ModelForm] = None,
        field_overrides: dict[str, QuerySet] = None,
        **kwargs
    ):
        # Parse fields to extract ForeignKeyField instances
        parsed_field_names, parsed_overrides = self._parse_fields_param(fields)

        super().__init__(**kwargs)
        self.fields = parsed_field_names
        self.exclude = exclude
        self.form_class = form_class
        self.field_overrides = field_overrides or parsed_overrides or {}

        if exclude:
            if fields:
                raise ValueError('Must only pass one of fields, exclude, or form_class')

        if form_class:
            if exclude:
                raise ValueError('Cannot use both form_class and exclude')

        # Validate that field_overrides are for actual ForeignKey fields
        self._validate_field_overrides()

    @classmethod
    def from_proxy_registry_data(
        cls,
        form_class_path: str | None = None,
        field_overrides_serialized: dict[str, str] | None = None,
        **kwargs
    ) -> GlueProxyModelFieldsMixin:
        if form_class_path:
            form_class = get_class_from_path_string(form_class_path)
        else:
            form_class = None

        # Deserialize field overrides
        field_overrides = None
        if field_overrides_serialized:
            field_overrides = {
                field_name: deserialize_queryset(encoded_query)
                for field_name, encoded_query in field_overrides_serialized.items()
            }

        return cls(
            form_class=form_class,
            field_overrides=field_overrides,
            **kwargs
        )

    @abstractmethod
    def get_model_class(self):
        """Return the Django model class associated with this proxy."""
        raise NotImplementedError("Subclasses must implement get_model_class()")

    @classmethod
    def _parse_fields_param(cls, fields: Sequence) -> tuple[list[str], dict[str, QuerySet]]:
        """Parse fields param into field names and queryset overrides."""
        from django_glue.shortcuts import ForeignKeyField

        field_names = []
        field_overrides = {}
        for item in fields:
            if isinstance(item, ForeignKeyField):
                field_names.append(item.name)
                field_overrides[item.name] = item.queryset
            else:
                field_names.append(item)
        return field_names, field_overrides

    def _validate_field_overrides(self):
        """Validate that field_overrides are for actual ForeignKey fields."""
        if not self.field_overrides:
            return

        model_class = self.get_model_class()
        for field_name in self.field_overrides.keys():
            try:
                field = model_class._meta.get_field(field_name)
            except Exception:
                raise ValueError(
                    f"Field '{field_name}' does not exist on model '{model_class.__name__}'"
                )

            if field.__class__.__name__ not in ('ForeignKey', 'OneToOneField'):
                raise ValueError(
                    f"Field '{field_name}' is not a ForeignKey or OneToOneField. "
                    f"Glue.ForeignKeyField can only be used with ForeignKey fields."
                )

    def to_session_data(self) -> dict:
        session_data = super().to_session_data()
        if self.form_class:
            session_data.update({
                'form_class_path': f'{self.form_class.__module__}.{self.form_class.__name__}',
            })

        if self.fields:
            session_data.update({
                'fields': list(self.fields)
            })

        if self.exclude:
            session_data.update({
                'exclude': list(self.exclude)
            })

        if self.field_overrides:
            session_data.update({
                'field_overrides_serialized': {
                    field_name: serialize_queryset(queryset)
                    for field_name, queryset in self.field_overrides.items()
                }
            })

        return session_data | self._build_session_data()

    @cached_property
    def _included_fields(self) -> dict[str, Any]:
        # TODO: we should probably ensure id is in included fields due to how we are
        # queryset instance updates

        deconstructed_fields = [
            field.deconstruct()
            for field in self.get_model_class()._meta.get_fields()
            if field.name == 'id' or (
                not isinstance(field, ForeignObjectRel) and
                not field.__class__.__name__ == 'GenericRelation' and
                not field.name in self.exclude and
                (not self.fields or field.name in self.fields) and
                (not self.form_class or field.name in self.form_class().fields.keys())
            )
        ]

        # Options to exclude from field metadata (not JSON serializable or not needed)
        excluded_options = {'default', 'validators', 'on_delete'}

        fields = {
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

        # Add choices from field overrides (custom querysets)
        for field_name, queryset in self.field_overrides.items():
            if field_name in fields:
                fields[field_name]['choices'] = [
                    (obj.pk, str(obj)) for obj in queryset
                ]

        return fields

    def _get_form_instance(self, payload: dict) -> BaseForm:
        if self.form_class:
            base_class = self.form_class
        else:
            base_class = modelform_factory(
                self.get_model_class(),
                fields=payload.keys()
            )

        # Create ModelChoiceFields with custom querysets
        overrides = {
            name: ModelChoiceField(queryset=qs)
            for name, qs in self.field_overrides.items()
            if name in payload.keys()
        }

        if not overrides:
            return base_class(data=payload)

        # Dynamically create subclass with overridden fields
        form_class = type('GlueProxyModelFieldsMixinForm', (base_class,), overrides)

        return form_class(data=payload)

    def _validate_payload(self, payload: dict) -> dict:
        # Filter payload to only include allowed fields
        filtered_payload = {
            field_name: value
            for field_name, value in payload.items()
            if field_name in self._included_fields
        }

        if not filtered_payload:
            return {}

        form = self._get_form_instance(filtered_payload)

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
