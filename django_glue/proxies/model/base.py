"""
Base class for Django Glue model proxies.

Provides field inclusion/exclusion filtering and form-based validation
for proxies that work with Django model fields.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from django.db.models import Model
from django.forms import modelform_factory, model_to_dict
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

    def _save(self, cleaned_data: dict) -> dict:
        model_instance = self._get_model_instance()
        for field_name, field_data in cleaned_data.items():
            if isinstance(field_data, Sequence):
                # TODO: need to make this check more comprehensive
                getattr(model_instance, field_name).set(field_data)
            else:
                setattr(model_instance, field_name, field_data)

        # TODO: possibly add ability for custom save logic here (e.g. service save model object pipelines)?
        model_instance.save()

        return model_to_dict(model_instance)
