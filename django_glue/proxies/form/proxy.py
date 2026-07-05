from __future__ import annotations

from abc import ABC
from typing import Self, cast

from django.forms.forms import BaseForm
from django.http import HttpRequest

from django_glue.access.access import GlueAccess
from django_glue.proxies.decorators import action
from django_glue.proxies.form.contract import GlueFormProxyContractData
from django_glue.proxies.form.state import GlueFormProxyState
from django_glue.proxies.proxy import BaseGlueProxy
from django_glue.resolver.action.schemas import ActionRequest
from django_glue.utils import get_attr_from_path_string


class GlueFormProxy(BaseGlueProxy):
    """
    Mixin providing form-related functionality for proxies.

    Provides:
    - Field definition extraction for frontend
    - Form validation logic
    - Error serialization
    - validate() and save() actions
    - Response proxy_state with form errors
    """

    def __init__(
            self,
            form_instance: BaseForm,
            namespace: str = 'form',
            **kwargs
        ) -> None:
        self.form_instance = form_instance

        form_class = self.form_instance.__class__
        self.form_class_path = f'{form_class.__module__}.{form_class.__name__}'

        self._register_actions_for_class(target_class=self.form_instance.__class__)

        super().__init__(
            **kwargs,
            namespace=namespace
        )

    @classmethod
    def _from_action_request(cls, action_request: ActionRequest) -> Self:
        contract_data = GlueFormProxyContractData.model_validate(
            action_request.contract.custom_data
        )

        if not contract_data.form_class_path:
            raise ValueError()

        form_class = cast(
            'type[BaseForm]', get_attr_from_path_string(contract_data.form_class_path)
        )

        if action_request.state:
            state_data = GlueFormProxyState.model_validate(action_request.state)
            form = form_class(initial=state_data.instance_data, files=state_data.files)
        else:
            form = form_class()

        return cls(
            name=action_request.contract.name,
            access=action_request.contract.access,
            form_instance=form
        )


    @property
    def _field_metadata(self) -> dict:
        """Extract field definitions from the form to aid in frontend rendering."""
        form = self.form_instance

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

    @property
    def _custom_contract_data(self) -> dict:
        form_class = self.form_instance.__class__

        return {
            'fields': self._field_metadata,
            'form_class_path': f'{form_class.__module__}.{form_class.__name__}',
        }

    @property
    def state(self) -> GlueFormProxyState:
        return GlueFormProxyState(
            instance_data=self.form_instance.data,
            errors=self.form_instance.errors,
            files=self.form_instance.files
        )

    @property
    def errors(self) -> dict:
        """Convert Django ErrorDict to JSON-serializable dict."""
        self.form_instance.is_valid()
        return self.form_instance.errors

    @action(access=GlueAccess.CHANGE)
    def validate(self, request: HttpRequest) -> dict:
        return {'valid': bool(self.errors)}

    @action(access=GlueAccess.VIEW)
    def foreign_key_choices(
        self,
        request,
        field_name: str | None = None
    ) -> list:
        """Get choices for a foreign key field."""
        if not field_name:
            return []

        field = self.form_instance.fields[field_name]

        if field.__class__.__name__ not in ['ModelChoiceField', 'ModelMultipleChoiceField']:
            return []


        return [[obj.pk, f'{obj}'] for obj in field.queryset.all()]
