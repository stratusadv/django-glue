from __future__ import annotations

from abc import ABC
from itertools import chain
from typing import TYPE_CHECKING, Any, Sequence, cast

from django.core.exceptions import FieldDoesNotExist
from django.db import transaction
from django.db.models import Model
from django.db.models.fields import BinaryField
from django.forms import modelform_factory
from django.forms.models import ModelMultipleChoiceField
from django.forms.models import ModelForm

from django_glue.access.access import GlueAccess
from django_glue.bound_attributes.decorators import Attribute
from django_glue.proxies.form.proxy import GlueFormProxy
from django_glue.proxies.model.instance.state import GlueModelInstanceProxyState

if TYPE_CHECKING:
    from django.http import HttpRequest


class BaseGlueModelProxy(GlueFormProxy, ABC):
    """Base class for model proxies — adds field inclusion/exclusion and model-specific bound attributes."""

    _subject_type = Model

    @staticmethod
    def _model_field_names(model_class: type[Model]) -> list[str]:
        return [
            field.name for field in chain(
                model_class._meta.fields,
                model_class._meta.many_to_many,
            )
            if not isinstance(field, BinaryField)
        ]

    @staticmethod
    def _editable_model_field_names(model_class: type[Model], field_names: Sequence[str]) -> list[str]:
        editable_field_names = []

        for field_name in field_names:
            try:
                field = model_class._meta.get_field(field_name)
            except FieldDoesNotExist:
                continue

            if field.editable:
                editable_field_names.append(field_name)

        return editable_field_names

    @staticmethod
    def _normalize_included_field_names(fields: Sequence | dict, exclude: Sequence[str]) -> list[str]:
        excluded = set(exclude)
        return [
            field_name
            for field_name in dict.fromkeys(fields)
            if field_name not in excluded
        ]

    @staticmethod
    def _serialize_model_instance(model_instance: Model, field_names: Sequence[str]) -> dict:
        data = {}

        for field_name in field_names:
            try:
                field = model_instance._meta.get_field(field_name)
            except FieldDoesNotExist:
                continue

            if field.many_to_many:
                if model_instance.pk is None:
                    data[field_name] = []
                else:
                    data[field_name] = list(field.value_from_object(model_instance))
            else:
                data[field_name] = field.value_from_object(model_instance)

        return data

    @classmethod
    def _build_state(
        cls,
        model_instance: Model,
        fields: Sequence | dict = (),
        exclude: Sequence[str] = (),
        form_class: type[ModelForm] | None = None,
    ) -> tuple[GlueModelInstanceProxyState, str | None, list[str]]:
        form_class_path = None
        model_class = model_instance.__class__
        if form_class:
            if not issubclass(form_class, ModelForm):
                msg = 'form_class must be a subclass of ModelForm'
                raise ValueError(msg)
            form_class_path = f'{form_class.__module__}.{form_class.__name__}'
            included_fields = list(form_class.base_fields)
            if fields != ():
                included_fields = list(fields)
            included_fields = cls._normalize_included_field_names(included_fields, exclude)

        if form_class is None:
            if fields == ():
                fields = cls._model_field_names(model_class)
            included_fields = cls._normalize_included_field_names(fields, exclude)
            editable_fields = cls._editable_model_field_names(model_class, included_fields)
            form_class = modelform_factory(
                model_class,
                fields=editable_fields,
            )

        form_instance = form_class(instance=model_instance)
        state = GlueModelInstanceProxyState(model=model_instance, form=form_instance)
        return state, form_class_path, included_fields

    @property
    def _included_field_names(self) -> list[str]:
        policy = getattr(self, 'policy', None)
        if policy:
            return list(policy.subject_details.included_fields.keys())

        return getattr(self, '_policy_included_field_names', list(self.state.form.fields))

    @staticmethod
    def _metadata_for_model_field(field) -> dict:
        field_def = {
            'type': field.__class__.__name__,
            'required': not getattr(field, 'blank', False) and not getattr(field, 'null', False),
            'disabled': not field.editable,
            'label': str(field.verbose_name) if getattr(field, 'verbose_name', None) else field.name,
            'help_text': str(field.help_text) if getattr(field, 'help_text', None) else '',
            'widget': 'ReadOnlyInput' if not field.editable else 'TextInput',
            'editable': field.editable,
        }

        if getattr(field, 'choices', None):
            field_def['choices'] = [(str(value), str(label)) for value, label in field.choices]

        max_length = getattr(field, 'max_length', None)
        if max_length:
            field_def['max_length'] = max_length

        return field_def

    @property
    def _field_metadata(self) -> dict:
        form_field_metadata = super()._field_metadata
        included_field_names = self._included_field_names
        metadata = {}
        model_class = self.state.model.__class__

        for field_name in included_field_names:
            try:
                model_field = model_class._meta.get_field(field_name)
            except FieldDoesNotExist:
                if field_name in form_field_metadata:
                    metadata[field_name] = form_field_metadata[field_name]
                continue

            if field_name in form_field_metadata:
                metadata[field_name] = {
                    **form_field_metadata[field_name],
                    'editable': model_field.editable,
                    'disabled': form_field_metadata[field_name]['disabled'] or not model_field.editable,
                }
            else:
                metadata[field_name] = self._metadata_for_model_field(model_field)

        return metadata

    @property
    def _custom_policy_details(self) -> dict:
        parent_details = super()._custom_policy_details

        model_class = self.state.model.__class__
        policy_data = {
            'model_class_path': f'{model_class.__module__}.{model_class.__name__}',
        }

        form_class_path = getattr(self, '_form_class_path', None)
        if form_class_path:
            parent_details['form_class_path'] = form_class_path
        else:
            parent_details.pop('form_class_path', None)

        return policy_data | parent_details

    def serialize_state(self) -> dict:
        return self.state.serialize(field_names=self._included_field_names)

    def _set_m2m_fields(self, field_data: dict) -> None:
        model_instance = self.state.model
        model_meta = model_instance._meta

        for field in chain(model_meta.many_to_many, model_meta.private_fields):
            if not hasattr(field, 'save_form_data'):
                continue
            if field.name in field_data:
                field.save_form_data(model_instance, field_data[field.name])

    @property
    def targets(self) -> list[Any]:
        return [self.state.model, *super().targets]

    @Attribute(access=GlueAccess.VIEW)
    def get(self, request: HttpRequest) -> dict:
        data = self._serialize_model_instance(self.state.model, list(self._field_metadata.keys()))

        for key, value in data.items():
            if isinstance(self.state.form.fields.get(key), ModelMultipleChoiceField):
                data[key] = [
                    {'pk': item.pk, '__str__': str(item)}
                    for item in value
                ]

        return data

    @Attribute(access=GlueAccess.DELETE)
    def delete(self, request: HttpRequest) -> None:
        self.state.model.delete()

    @transaction.atomic
    @Attribute(access=GlueAccess.CHANGE)
    def save(self, request: HttpRequest) -> None:
        if not self.state.errors:
            cast('ModelForm', self.state.form).save()
