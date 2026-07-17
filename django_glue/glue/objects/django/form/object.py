from __future__ import annotations

from functools import cached_property
from typing import Any

from django import forms
from django.http import HttpRequest

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
        request: HttpRequest,
        name: str,
        access: GlueAccess,
    ) -> None:
        super().__init__(request=request, name=name, access=access)
        self.form = form

    @property
    def subjects(self) -> dict[str, Any]:
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
        print(self)
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
        return {
            'instance_data': dict(self.form.data) if self.form.is_bound else self.form.initial,
            'errors': dict(self.form.errors),
        }

    @cached_property
    def metadata(self) -> GlueMetadata:
        return GlueMetadata.from_payload({
            'namespace': self.namespace,
            'fields': {
                name: self.attributes[name].metadata
                for name in self.form.fields
            },
            'attributes': {
                name: attribute.metadata
                for name, attribute in self.attributes.items()
                if name not in self.form.fields
            },
        })

    @classmethod
    def from_policy(cls, policy: GluePolicy, request: HttpRequest) -> FormGlue:
        form_class = get_attr_from_path_string(policy.identity['form_class_path'])
        glue_object = cls(
            form_class(),
            request=request,
            name=policy.name,
            access=policy.access,
        )
        glue_object.policy = policy
        return glue_object

    @Attribute(access=GlueAccess.VIEW)
    def load(self) -> dict[str, Any]:
        return {'state': self.state}

    @Attribute(access=GlueAccess.CHANGE)
    def validate(self, state: dict[str, Any], request: HttpRequest) -> dict[str, Any]:
        bound_form = self._bind_form(state, request)
        return {'valid': bound_form.is_valid(), 'errors': dict(bound_form.errors)}

    @Attribute(access=GlueAccess.CHANGE)
    def save(self, state: dict[str, Any], request: HttpRequest) -> dict[str, Any]:
        bound_form = self._bind_form(state, request)
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

    def _bind_form(
        self,
        state: dict[str, Any],
        request: HttpRequest,
    ) -> forms.BaseForm:
        self._resolve_instance()
        form_class = self.form.__class__
        kwargs = {
            'data': state.get('instance_data', {}),
            'files': request.FILES or None,
        }
        if isinstance(self.form, forms.ModelForm) and getattr(self.form, 'instance', None) is not None:
            kwargs['instance'] = self.form.instance
        return form_class(**kwargs)
