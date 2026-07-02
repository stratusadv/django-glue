from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from django.forms.forms import BaseForm

from django_glue.access.access import GlueAccess
from django_glue.proxies.decorators import action

if TYPE_CHECKING:
    from django_glue.resolver.action.schemas import ActionPayloadSchema


class GlueFormProxyMixin(ABC):
    """
    Mixin providing form-related functionality for proxies.

    Provides:
    - Field definition extraction for frontend
    - Form validation logic
    - Error serialization
    - validate() and save() actions
    - Response proxy_data with form errors
    """

    def get_response_proxy_data(
        self,
        action: str,
        action_payload: 'ActionPayloadSchema'
    ) -> dict | None:
        """
        Return form state in response proxy_data.

        Includes:
        - errors: Form validation errors (if any)
        - form_values: Current field values
        """
        action_target = getattr(self, '_last_action_target', None)
        if action_target is None:
            return None

        # Check if action target is a form
        if not hasattr(action_target, 'data'):
            return None

        proxy_data = {}

        # Include form errors if present
        if hasattr(action_target, 'errors') and action_target.errors:
            proxy_data['errors'] = self._serialize_errors(action_target.errors)

        # Include current form values
        if action_target.data:
            proxy_data['form_values'] = dict(action_target.data)

        return proxy_data if proxy_data else None

    @abstractmethod
    def _get_form_class(self) -> type[BaseForm]:
        """Return the form class to use for validation and field extraction."""

    def _get_form_instance(self, data: dict | None = None, files: dict | None = None) -> BaseForm:
        """Create a form instance."""
        form_class = self._get_form_class()
        if data is not None:
            for field_name, field in self._form_field_definitions.items():
                # Ensure that Multiple choice fields have list values. This is to prevent
                # errors when the frontend sends single values for multiple choice fields.
                if field['type'] in ['ModelMultipleChoiceField', 'MultipleChoiceField']:
                    value = data.get(field_name)
                    if value and not isinstance(value, list):
                        data[field_name] = [value]

            return form_class(data=data, files=files)

        return form_class()

    @property
    def _form_field_definitions(self) -> dict:
        """Extract field definitions from the form to aid in frontend rendering."""
        form = self._get_form_class()()

        # Get editable form fields from form
        fields = {}
        for name, field in form.fields.items():
            field_def = {
                'type': field.__class__.__name__,
                'required': field.required,
                'disabled': field.disabled,
                'label': str(field.label) if field.label else name,
                'help_text': str(field.help_text) if field.help_text else '',
                'widget': field.widget.__class__.__name__,
                'editable': True,
            }

            if hasattr(field, 'choices') and field.choices:
                field_def['choices'] = [(str(value), str(label)) for value, label in field.choices]
            if hasattr(field, 'max_length') and field.max_length:
                field_def['max_length'] = field.max_length
            if hasattr(field, 'min_length') and field.min_length:
                field_def['min_length'] = field.min_length
            fields[name] = field_def

        return fields

    def _serialize_errors(self, errors) -> dict:
        """Convert Django ErrorDict to JSON-serializable dict."""
        return {field: list(error_list) for field, error_list in errors.items()}

    def _save(self, cleaned_data) -> None:
        """
        Override in subclasses to customize the save behaviour and save response format.
        """
        return

    @action(access=GlueAccess.CHANGE)
    def validate(self, request, proxy_data: dict = None, file_data: dict = None) -> dict:
        """Validate form data without saving."""
        form_values = proxy_data.get('form_values', {}) if proxy_data else {}
        form = self._get_form_instance(data=form_values or None, files=file_data)

        is_valid = form.is_valid()

        return {
            'success': is_valid,
            'errors': None if is_valid else self._serialize_errors(form.errors),
            'cleaned_data': form.cleaned_data if is_valid else {},
        }

    @action(access=GlueAccess.CHANGE)
    def save(self, request, proxy_data: dict = None, file_data: dict = None) -> dict:
        """Validate and save form data."""
        validation_result = self.validate(request, proxy_data=proxy_data, file_data=file_data)

        if validation_result['success']:
            self._save(validation_result['cleaned_data'])

        return validation_result

    @action(access=GlueAccess.VIEW)
    def foreign_key_choices(self, request, field_definition: list = None) -> list:
        """Get choices for a foreign key field."""
        if (
            not field_definition
            or not isinstance(field_definition, (list, tuple))
            or len(field_definition) < 2
        ):
            return []
        field_name, field_data = field_definition

        if field_data.get('type', None) not in ['ModelChoiceField', 'ModelMultipleChoiceField']:
            return []

        field = self._get_form_class()().fields[field_name]

        return [[obj.pk, f'{obj}'] for obj in field.queryset.all()]
