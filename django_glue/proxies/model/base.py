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
from django.forms import modelform_factory, model_to_dict, FileField
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
        fields: Sequence = (),
        exclude: Sequence[str] = (),
        form_class: type[ModelForm] | None = None,
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
    ) -> GlueModelProxyBase:
        from django_glue.utils import get_class_from_path_string

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
    def get_model_class(self) -> type[Model]:
        """Return the Django model class associated with this proxy."""
        raise NotImplementedError("Subclasses must implement get_model_class()")

    @abstractmethod
    def _get_model_instance(self) -> Model:
        """Return the model instance for form binding."""
        raise NotImplementedError("Subclasses must implement _get_model_instance()")

    def _get_form_class(self) -> type[BaseForm]:
        if self.form_class:
            return self.form_class
        return modelform_factory(
            self.get_model_class(),
            fields=list(self.fields) if self.fields else '__all__',
            exclude=list(self.exclude) if self.exclude else ()
        )

    def _get_form_instance(
        self, data: dict | None = None, files: dict | None = None
    ) -> BaseForm:
        """Create a form instance bound to the model instance."""
        form_class = self._get_form_class()
        instance = self._get_model_instance()
        if data is not None:
            return form_class(data=data, instance=instance, files=files)
        return form_class(instance=instance)

    @property
    def _form_field_definitions(self) -> dict:
        """
        Extract field definitions from the form to aid in frontend rendering.

        Overrides the base implementation to always include the 'id' field
        for model-based proxies, since modelform_factory excludes primary keys.
        """
        fields = super()._form_field_definitions

        if 'id' not in fields:
            fields['id'] = {
                'type': 'AutoField',
                'required': False,
                'label': 'ID',
                'help_text': '',
                'widget': 'HiddenInput',
            }

        return fields

    def _build_context_data(self) -> dict:
        context_data = super()._build_context_data()
        context_data.update({
            'fields': self._form_field_definitions,
            'exclude': list(self.exclude)
        })

        if self.form_class:
            context_data.update({
                'form_class_path': f'{self.form_class.__module__}.{self.form_class.__name__}',
            })

        return context_data

    def _set_non_m2m_fields(self, field_data: dict):
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
            f"{field.name}_id" for field in model_fields
            if f"{field.name}_id" in field_data and field.many_to_one and field.name not in updated_fields
        ]

        for field_name in foreign_key_id_aliases:
            setattr(model_instance, field_name, field_data[field_name])

        # Update file fields deferred from earlier
        for field in file_field_list:
            field.save_form_data(model_instance, field_data[field.name])

    def _set_m2m_fields(self, field_data: dict):
        model_instance = self._get_model_instance()
        model_meta = model_instance._meta

        for field in chain(model_meta.many_to_many, model_meta.private_fields):
            if not hasattr(field, "save_form_data"):
                continue
            if field.name in field_data:
                field.save_form_data(model_instance, field_data[field.name])

    @transaction.atomic
    def _save(self, field_data: dict) -> dict:
        model_instance = self._get_model_instance()

        self._set_non_m2m_fields(field_data)
        model_instance.save()
        self._set_m2m_fields(field_data)

        return model_to_dict(model_instance)
