from __future__ import annotations

from functools import cached_property
from typing import TYPE_CHECKING, Any

from django import forms
from django.forms.models import model_to_dict

from django_glue.access import GlueAccess
from django_glue.glue.attributes import BaseGlueAttribute
from django_glue.glue.base import BaseGlue
from django_glue.glue.attributes.django.form import FormFieldAttribute
from django_glue.glue.attributes import DeclaredAttribute
from django_glue.glue.loading import LoadingStrategy
from django_glue.utils import get_attr_from_path_string

if TYPE_CHECKING:
    from django_glue.glue.policy import GluePolicy


class FormGlue(BaseGlue):
    namespace = 'form'

    def __init__(
        self,
        form: forms.BaseForm,
        *,
        name: str,
        access: GlueAccess,
        loading_strategy: LoadingStrategy = LoadingStrategy.LAZY,
    ) -> None:
        super().__init__(name=name, access=access, loading_strategy=loading_strategy)
        self.form = form
        self._loaded_state: dict[str, Any] | None = None
        self._field_errors: dict[str, list[str]] = {}

    def get_attribute_providers(self) -> dict[str, Any]:
        return {'form': self.form}

    def get_identity(self) -> dict[str, Any]:
        return {
            'form_class_path': f'{self.form.__class__.__module__}.{self.form.__class__.__name__}',
            'target_pk': getattr(getattr(self.form, 'instance', None), 'pk', None),
            'initial': self._prepared_initial,
        }

    @property
    def _prepared_initial(self) -> dict[str, Any]:
        return {
            name: field.prepare_value(self._ordered(value)) if field else value
            for name, value in self.form.initial.items()
            for field in [self.form.fields.get(name)]
        }

    @staticmethod
    def _ordered(value: Any) -> Any:
        """Return `value` with a deterministic iteration order.

        A ManyToMany (or other unordered) queryset has no guaranteed row order, so two
        evaluations of the "same" relation can iterate in a different order even though
        the underlying data hasn't changed. That's fatal here: this value feeds a signed
        GluePolicy, and a reordering alone would change the serialized bytes and therefore
        the signature, producing a spurious "policy has been tampered with" error. Sorting
        by pk before `field.prepare_value()` sees it removes that nondeterminism regardless
        of what prepare_value does with the value (return model instances, pks, etc).
        """
        if hasattr(value, '__iter__') and not isinstance(value, str) and not hasattr(value, '_meta'):
            try:
                return sorted(value, key=lambda item: getattr(item, 'pk', item))
            except TypeError:
                return value
        return value

    @cached_property
    def attributes(self) -> dict[str, BaseGlueAttribute]:
        return super().attributes | {
            name: FormFieldAttribute(
                owner=self,
                name=name,
                field=field,
                form=self.form,
                required_access=GlueAccess.VIEW if field.disabled else GlueAccess.CHANGE,
            )
            for name, field in self.form.fields.items()
        }

    def get_state(self) -> dict[str, Any]:
        self._populate_field_errors()
        return {
            name: attribute.state
            for name, attribute in self.attributes.items()
            if hasattr(attribute, 'state')
        }

    def _populate_field_errors(self) -> None:
        """Populate _field_errors from form errors."""
        self._field_errors = dict(self.form.errors)

    def get_metadata(self) -> dict[str, Any]:
        return {
            'attributes': {
                name: attribute.metadata
                for name, attribute in self.attributes.items()
            },
        }

    @classmethod
    def _reconstruct_from_policy(cls, policy: GluePolicy) -> FormGlue:
        form_class = get_attr_from_path_string(policy.identity['form_class_path'])
        initial = policy.identity.get('initial', {})
        target_pk = policy.identity.get('target_pk')

        if target_pk is not None and issubclass(form_class, forms.ModelForm):
            model_class = form_class._meta.model
            try:
                instance = model_class.objects.get(pk=target_pk)
                model_initial = model_to_dict(
                    instance,
                    form_class._meta.fields,
                    form_class._meta.exclude,
                )
                initial = {**model_initial, **initial}
                form = form_class(instance=instance, initial=initial)
            except model_class.DoesNotExist:
                form = form_class(initial=initial)
        else:
            form = form_class(initial=initial)

        return cls(form, name=policy.name, access=policy.access)

    def _load_client_state(self, state: dict[str, Any]) -> None:
        """Bind client-provided state before executing form attributes."""
        self._loaded_state = state
        self.form = self._bind_form()

    @DeclaredAttribute(required_access=GlueAccess.CHANGE)
    def validate(self) -> dict[str, Any]:
        bound_form = self._bind_form()
        return {'valid': bound_form.is_valid(), 'errors': dict(bound_form.errors)}

    @DeclaredAttribute(required_access=GlueAccess.CHANGE)
    def save(self) -> dict[str, Any]:
        bound_form = self._bind_form()
        valid = bound_form.is_valid()
        if valid and hasattr(bound_form, 'save'):
            bound_form.save()
        return {'valid': valid, 'errors': dict(bound_form.errors)}

    # Choice loading is read-only; returning form state would trigger validation during serialization.
    @DeclaredAttribute(required_access=GlueAccess.VIEW, takes_client_state=False, updates_client_state=False)
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

        def serialize_choice(obj: Any) -> dict[str, Any]:
            choice_obj = {'pk': obj.pk, '__str__': f'{obj}'}
            for choice_field in choice_fields or []:
                choice_obj[choice_field] = getattr(obj, choice_field)
            return {
                'value': obj.pk,
                'label': f'{obj}',
                'obj': choice_obj,
            }

        return [serialize_choice(obj) for obj in queryset.all()]

    def _bind_form(self) -> forms.BaseForm:
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
        has_instance = getattr(self.form, 'instance', None) is not None
        if isinstance(self.form, forms.ModelForm) and has_instance:
            kwargs['instance'] = self.form.instance
        return form_class(**kwargs)
