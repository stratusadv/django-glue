from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.forms.forms import BaseForm

from django_glue.access.access import GlueAccess
from django_glue.bound_attributes.decorators import Attribute
from django_glue.proxies.form.state import GlueFormProxyState
from django_glue.proxies.proxy import BaseGlueProxy

if TYPE_CHECKING:
    from django.http import HttpRequest


class GlueFormProxy(BaseGlueProxy):
    """Proxy for a Django form. Provides field metadata, validation, and save operations."""

    _subject_type = BaseForm
    _state_class = GlueFormProxyState

    @classmethod
    def register(
        cls,
        request: HttpRequest,
        target: BaseForm,
        name: str,
        access: GlueAccess = GlueAccess.VIEW,
        namespace: str = 'form',
    ) -> None:
        from django_glue.proxies.form.state import GlueFormProxyState  # noqa: PLC0415

        state = GlueFormProxyState(form=target)
        proxy = cls(name=name, namespace=namespace, access=access, state=state)
        proxy._register_with_request(request)

    @property
    def targets(self) -> list:
        return [self.state.form, *super().targets]

    @property
    def _field_metadata(self) -> dict:
        form = self.state.form
        fields = {}
        for field_name, field in form.fields.items():
            field_def = {
                'type': field.__class__.__name__,
                'required': field.required,
                'disabled': field.disabled,
                'label': str(field.label) if field.label else field_name,
                'help_text': str(field.help_text) if field.help_text else '',
                'widget': field.widget.__class__.__name__,
                'editable': True,
            }
            if hasattr(field, 'queryset'):
                field_def['choices'] = []
                field_def['pk_field'] = field.queryset.model._meta.pk.name
                field_def['choice_model_path'] = (
                    f'{field.queryset.model.__module__}.{field.queryset.model.__name__}'
                )
                field_def['choices_cache_key'] = (
                    f'{form.__class__.__module__}.{form.__class__.__name__}.'
                    f'{field_name}.{field.queryset.model._meta.label_lower}'
                )
            elif hasattr(field, 'choices') and field.choices:
                field_def['choices'] = [(str(value), str(label)) for value, label in field.choices]

            if hasattr(field, 'max_length') and field.max_length:
                field_def['max_length'] = field.max_length
            if hasattr(field, 'min_length') and field.min_length:
                field_def['min_length'] = field.min_length
            fields[field_name] = field_def
        return fields

    @property
    def _custom_policy_details(self) -> dict:
        form_class_path = f'{self.state.form.__class__.__module__}.{self.state.form.__class__.__name__}'

        details = {
            'included_fields': self._field_metadata,
            'form_class_path': form_class_path,
            'target_pk': self.state.target_pk
        }

        model_instance = getattr(self.state.form, 'instance', None)

        if model_instance:
            details.update({
                'pk_field_name': model_instance.__class__._meta.pk.name,
                'target_pk': model_instance.pk,
            })

        return details

    @Attribute(access=GlueAccess.CHANGE)
    def validate(self, request: HttpRequest) -> dict:
        return {'valid': not bool(self.state.errors)}

    @Attribute(access=GlueAccess.VIEW)
    def foreign_key_choices(
        self,
        request: HttpRequest,
        field_name: str | None = None,
        choice_fields: list[str] | None = None,
    ) -> list:
        if not field_name:
            return []
        field = self.state.form.fields[field_name]
        if field.__class__.__name__ not in ('ModelChoiceField', 'ModelMultipleChoiceField'):
            return []

        def serialize_choice(obj) -> dict[str, Any]:
            choice = {'pk': obj.pk, '__str__': f'{obj}'}
            for choice_field in choice_fields or []:
                choice[choice_field] = getattr(obj, choice_field)
            return choice

        return [serialize_choice(obj) for obj in field.queryset.all()]

    @Attribute(access=GlueAccess.VIEW)
    def load(self, request: HttpRequest) -> None:
        pass

    @Attribute(access=GlueAccess.CHANGE)
    def save(self, request: HttpRequest) -> None:
        if not self.state.errors:
            self.state.form.save()
