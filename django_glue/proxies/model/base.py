"""
Base class for Django Glue model proxies.

Provides field inclusion/exclusion filtering and form-based validation
for proxies that work with Django model fields.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from itertools import chain

from django.db import transaction
from django.db.models import Model, AutoField
from django.forms import modelform_factory, FileField
from django.forms.forms import BaseForm
from django.forms.models import ModelForm

from django_glue.proxies.form.mixin import GlueFormProxyMixin
from django_glue.proxies.proxy import BaseGlueProxy


class GlueModelProxyBase(GlueFormProxyMixin, BaseGlueProxy, ABC):
    """
    Base class for model-based proxies.

    Provides field filtering via include/exclude and uses Django's
    modelform_factory for validation. Inherits validate() and save()
    actions from GlueFormProxyMixin.

    Attributes:
        fields: Sequence of field names to include. If empty, all fields are included.
        exclude: Sequence of field names to exclude from the proxy.
        form_class: Optional custom ModelForm class for validation.

    """

    def __init__(
        self,
        fields: Sequence | dict = (),
        exclude: Sequence[str] = (),
        form_class: type[ModelForm] | None = None,
        **kwargs,
    ) -> None:
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
        **kwargs,
    ) -> GlueModelProxyBase:
        from django_glue.utils import get_class_from_path_string

        if form_class_path:
            form_class = get_class_from_path_string(form_class_path)
        else:
            form_class = None

        return cls(form_class=form_class, fields=fields, exclude=exclude, **kwargs)

    @abstractmethod
    def get_model_class(self) -> type[Model]:
        """Return the Django model class associated with this proxy."""
        message = 'Subclasses must implement get_model_class()'
        raise NotImplementedError(message)

    @abstractmethod
    def _get_model_instance(self) -> Model:
        """Return the model instance for form binding."""
        message = 'Subclasses must implement _get_model_instance()'
        raise NotImplementedError(message)

    def _get_form_class(self) -> type[BaseForm]:
        if self.form_class:
            return self.form_class

        form_fields = self.fields

        if isinstance(form_fields, dict):
            form_fields = [
                field_name for field_name, field in form_fields.items() if field.get('editable')
            ]

        return modelform_factory(
            self.get_model_class(),
            fields=list(form_fields) if form_fields else '__all__',
            exclude=list(self.exclude) if self.exclude else (),
        )

    @property
    def _model_field_definitions(self) -> dict:
        model = self.get_model_class()

        included_model_fields = [
            f for f in model._meta.get_fields()
            if not (f.is_relation and f.auto_created)
        ]
        if self.fields and isinstance(self.fields, Sequence):
            included_model_fields = [
                field for field in included_model_fields if field.name in self.fields
            ]
        if self.exclude:
            included_model_fields = [
                field for field in included_model_fields if field.name not in self.exclude
            ]

        return {
            field.name: {
                'type': field.__class__.__name__,
                'required': False,
                'label': field.name,
                'help_text': getattr(field, 'help_text', None),
                'editable': False,
                'widget': '',
            }
            for field in included_model_fields
        }

    @property
    def _form_field_definitions(self) -> dict:
        """
        Extract field definitions from the form to aid in frontend rendering.

        Overrides the base implementation to always include the 'id' field
        for model-based proxies, since modelform_factory excludes primary keys.
        """

        form_fields = super()._form_field_definitions
        non_form_fields = {
            field_name: field
            for field_name, field in self._model_field_definitions.items()
            if field_name not in form_fields
        }

        return {**super()._form_field_definitions, **non_form_fields}

    def _build_context_data(self) -> dict:
        context_data = super()._build_context_data()
        context_data.update({'fields': self._form_field_definitions, 'exclude': list(self.exclude)})

        if self.form_class:
            context_data.update(
                {'form_class_path': f'{self.form_class.__module__}.{self.form_class.__name__}'}
            )

        return context_data

    def _set_non_m2m_fields(self, field_data: dict) -> None:
        model_instance = self._get_model_instance()
        model_fields = model_instance._meta.fields

        file_field_list = []
        updated_fields = []

        for field in model_fields:
            if isinstance(field, AutoField) or field.name not in field_data:
                continue

            # Defer saving file-type fields until after the other fields, so a
            # callable upload_to can use the values from other fields (from django's construct_instance).
            if isinstance(field, FileField):
                file_field_list.append(field)
                updated_fields.append(field.name)
            else:
                field.save_form_data(model_instance, field_data[field.name])
                updated_fields.append(field.name)

        # Update foreign key id aliases in field_data for
        # related fields that weren't already updated above
        foreign_key_id_aliases = [
            f'{field.name}_id'
            for field in model_fields
            if f'{field.name}_id' in field_data
            and field.many_to_one
            and field.name not in updated_fields
        ]

        for field_name in foreign_key_id_aliases:
            setattr(model_instance, field_name, field_data[field_name])

        # Update file fields deferred from earlier
        for field in file_field_list:
            field.save_form_data(model_instance, field_data[field.name])

    def _set_m2m_fields(self, field_data: dict) -> None:
        model_instance = self._get_model_instance()
        model_meta = model_instance._meta

        for field in chain(model_meta.many_to_many, model_meta.private_fields):
            if not hasattr(field, 'save_form_data'):
                continue
            if field.name in field_data:
                field.save_form_data(model_instance, field_data[field.name])

    @transaction.atomic
    def _save(self, field_data: dict) -> None:
        model_instance = self._get_model_instance()

        self._set_non_m2m_fields(field_data)
        model_instance.save()
        self._set_m2m_fields(field_data)
