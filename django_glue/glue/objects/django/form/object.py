from __future__ import annotations

from functools import cached_property
from typing import Any

from django import forms

from django_glue.access import GlueAccess
from django_glue.glue.attributes import BaseGlueAttribute
from django_glue.glue.base import BaseGlue
from django_glue.glue.attributes.django.form import FormFieldAttribute
from django_glue.glue.policy import GluePolicy
from django_glue.glue.metadata import GlueMetadata
from django_glue.glue.attributes import Attribute
from django_glue.utils import get_attr_from_path_string


class FormGlue(BaseGlue):
    namespace = 'form'

    def __init__(
        self,
        form: forms.BaseForm,
        *,
        name: str,
        access: GlueAccess,
    ) -> None:
        super().__init__(name=name, access=access)
        self.form = form
        self._loaded_state: dict[str, Any] | None = None
        self._field_errors: dict[str, list[str]] = {}

    @property
    def attribute_providers(self) -> dict[str, Any]:
        return {'form': self.form}

    @property
    def identity(self) -> dict[str, Any]:
        return {
            'form_class_path': f'{self.form.__class__.__module__}.{self.form.__class__.__name__}',
            'target_pk': getattr(getattr(self.form, 'instance', None), 'pk', None),
        }

    @cached_property
    def attributes(self) -> dict[str, BaseGlueAttribute]:
        return super().attributes | {
            name: FormFieldAttribute(
                owner=self,
                name=name,
                field=field,
                form=self.form,
                access=GlueAccess.VIEW if field.disabled else GlueAccess.CHANGE,
            )
            for name, field in self.form.fields.items()
        }

    def _resolve_instance(self) -> None:
        if (
            isinstance(self.form, forms.ModelForm)
            and getattr(self.form, 'instance', None) is not None
            and self.form.instance.pk is None
            and hasattr(self, 'policy')
            and self.policy.identity.get('target_pk') is not None
        ):
            model_class = self.form._meta.model
            target_pk = self.policy.identity['target_pk']
            try:
                model_instance = model_class.objects.get(pk=target_pk)
                self.form.instance = model_instance
                from django.forms.models import model_to_dict
                opts = self.form._meta
                self.form.initial = model_to_dict(model_instance, opts.fields, opts.exclude)
            except model_class.DoesNotExist:
                pass

    @property
    def state(self) -> dict[str, Any]:
        self._resolve_instance()
        self._populate_field_errors()
        return {
            name: attribute.state
            for name, attribute in self.attributes.items()
            if hasattr(attribute, 'state')
        }

    def _populate_field_errors(self) -> None:
        """Populate _field_errors from form errors."""
        self._field_errors = dict(self.form.errors)

    @cached_property
    def metadata(self) -> GlueMetadata:
        return GlueMetadata.from_payload({
            'namespace': self.namespace,
            'attributes': {
                name: attribute.metadata
                for name, attribute in self.attributes.items()
            },
        })

    @classmethod
    def _from_policy(cls, policy: GluePolicy) -> FormGlue:
        form_class = get_attr_from_path_string(policy.identity['form_class_path'])
        glue_object = cls(
            form_class(),
            name=policy.name,
            access=policy.access,
        )
        glue_object.policy = policy
        return glue_object

    def _load_client_state(self, state: dict[str, Any]) -> None:
        """Bind client-provided state before executing form attributes."""
        self._loaded_state = state
        self.form = self._bind_form()

    @Attribute(access=GlueAccess.VIEW, loads_state=False)
    def load(self) -> dict[str, Any]:
        return {'state': self.state}

    @Attribute(access=GlueAccess.CHANGE)
    def validate(self) -> dict[str, Any]:
        bound_form = self._bind_form()
        return {'valid': bound_form.is_valid(), 'errors': dict(bound_form.errors)}

    @Attribute(access=GlueAccess.CHANGE)
    def save(self) -> dict[str, Any]:
        bound_form = self._bind_form()
        valid = bound_form.is_valid()
        if valid and hasattr(bound_form, 'save'):
            bound_form.save()
        return {'valid': valid, 'errors': dict(bound_form.errors)}

    @Attribute(access=GlueAccess.VIEW)
    def foreign_key_choices(
        self,
        field_name: str | None = None,
        choice_fields: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        if not field_name or field_name not in self.form.fields:
            return []

        field = self.form.fields[field_name]
        queryset = getattr(field, 'queryset', None)
        if queryset is None:
            return []

        def serialize_choice(obj) -> dict[str, Any]:
            choice = {'pk': obj.pk, '__str__': f'{obj}'}
            for choice_field in choice_fields or []:
                choice[choice_field] = getattr(obj, choice_field)
            return choice

        return [serialize_choice(obj) for obj in queryset.all()]

    def _bind_form(self) -> forms.BaseForm:
        self._resolve_instance()
        state = self._loaded_state or {}
        form_class = self.form.__class__
        # Extract values from new state structure: {field_name: {value: ..., errors: ...}}
        data = {
            field_name: field_state.get('value') if isinstance(field_state, dict) else field_state
            for field_name, field_state in state.items()
            if field_name in self.form.fields
        }
        kwargs = {
            'data': data,
            'files': self.request.FILES if self.request else None,
        }
        if isinstance(self.form, forms.ModelForm) and getattr(self.form, 'instance', None) is not None:
            kwargs['instance'] = self.form.instance
        return form_class(**kwargs)
