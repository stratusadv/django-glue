"""
Field handling mixin for Django Glue model proxies.

Provides field inclusion/exclusion filtering and payload validation
for proxies that work with Django model fields.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Sequence, TYPE_CHECKING

from django.apps import apps
from django.db.models import ForeignObjectRel, QuerySet, Model
from django.forms import modelform_factory, ModelChoiceField
from django.forms.forms import BaseForm
from django.forms.models import ModelForm
from django.utils.functional import cached_property

from django_glue import GlueAccess
from django_glue.exceptions import GluePayloadValidationError
from django_glue.proxies.decorators import action
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
        **kwargs
    ):
        super().__init__(**kwargs)
        self.fields = fields
        self.exclude = exclude
        self.form_class = form_class

    @classmethod
    def from_action_request_data(
        cls,
        form_class_path: str | None = None,
        fields: Sequence[str] = (),
        exclude: Sequence[str] = (),
        **kwargs
    ) -> GlueProxyModelFieldsMixin:
        if form_class_path:
            form_class = get_class_from_path_string(form_class_path)
        else:
            form_class = None

        return cls(
            form_class=form_class,
            fields=fields,
            exclude=exclude,
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

    def _build_context_data(self) -> dict:
        context_data = super()._build_context_data()
        context_data.update({
            'fields': self._included_fields,
            'exclude': list(self.exclude)
        })

        if self.form_class:
            context_data.update({
                'form_class_path': f'{self.form_class.__module__}.{self.form_class.__name__}',
            })

        return context_data

    @cached_property
    def _included_fields(self) -> dict[str, Any]:
        # TODO: we should probably ensure id is in included fields due to how we are
        # queryset instance updates

        model_fields = self.get_model_class()._meta.get_fields()

        deconstructed_fields = [
            field.deconstruct()
            for field in self.get_model_class()._meta.get_fields()
            if field.name == 'id' or (
                not field.__class__.__name__ == 'GenericRelation' and
                not field.__class__.__name__ == 'ManyToOneRel' and
                not field.name in self.exclude and
                (not self.fields or field.name in self.fields) and
                (not self.form_class or field.name in self.form_class().fields.keys())
            )
        ]

        # Options to exclude from field metadata (not JSON serializable or not needed)
        excluded_options = {'default', 'validators', 'on_delete'}

        fields = {}
        for field_name, field_type, _, field_options in deconstructed_fields:
            field_definition = {
                'type': field_type.rsplit('.', 1)[-1],  # Extract class name from full path
                **{
                    opt_name: opt_value
                    for opt_name, opt_value in field_options.items()
                    if opt_name not in excluded_options
                }
            }

            fields[field_name] = field_definition

        return fields

    def _get_form_instance(self, payload: dict) -> BaseForm:
        if self.form_class:
            form_class = self.form_class
        else:
            form_class = modelform_factory(
                self.get_model_class(),
                fields=payload.keys()
            )

        return form_class(data=payload)

    def _validate_save_payload(self, payload: dict) -> dict:
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

    @action(access=GlueAccess.VIEW)
    def foreign_key_choices(self, payload: dict):
        field_name, field_data = payload['field_definition']

        if not field_data.get('type', None) == 'ForeignKey':
            return []

        if self.form_class:
            field = self.form_class().fields[field_name]
        else:
            field = self.get_model_class()._meta.get_field(field_name)

        if isinstance(field, ModelChoiceField):
            return [
                [instance.pk, f'{instance}']
                for instance in field.queryset.values_list('pk', 'name')
            ]
        else:
            field_related_model = apps.get_model(field_data['to'])
            return [
                [instance.pk, f'{instance}']
                for instance in field_related_model.objects.all()
            ]
