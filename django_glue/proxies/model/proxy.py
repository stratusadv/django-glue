"""
Base class for Django Glue model proxies.

Provides field inclusion/exclusion filtering and form-based validation
for proxies that work with Django model fields.
"""

from __future__ import annotations

from abc import ABC
from itertools import chain
from typing import Self, Sequence, TypeVar, cast, TYPE_CHECKING

from django.db import transaction
from django.db.models import Model
from django.forms import model_to_dict, modelform_factory
from django.http import HttpRequest

from django_glue.access.access import GlueAccess
from django_glue.proxies.decorators import action
from django_glue.proxies.form.proxy import GlueFormProxy
from django_glue.proxies.form.state import GlueFormProxyState
from django_glue.proxies.model.contract import GlueModelProxyContractData
from django_glue.utils import get_attr_from_path_string
from django.forms.models import ModelForm


TModelContract = TypeVar('TModelContract', bound=GlueModelProxyContractData)


class BaseGlueModelProxy(GlueFormProxy, ABC):
    _subject_type = Model

    def __init__(
        self,
        model_instance: Model,
        fields: Sequence | dict = (),
        exclude: Sequence[str] = (),
        form_class: type[ModelForm] | None = None,
        **kwargs,
    ) -> None:
        self.model_instance = model_instance

        self.form_class_path = None
        if form_class:
            if not issubclass(form_class, ModelForm):
                raise ValueError()

            self.form_class_path = f'{form_class.__module__}.{form_class.__name__}'

        if not form_class:
            if fields == ():
                fields = [field.name for field in model_instance._meta.fields]

            form_class = modelform_factory(
                self.model_instance.__class__,
                fields=list(set(fields) - set(exclude)),
            )

        form = form_class(instance=self.model_instance)

        self._register_actions_for_class(self.model_instance.__class__)

        super().__init__(form_instance=form, **kwargs)

    @classmethod
    def _from_deconstructed_action_request_data(
        cls,
        name: str,
        access: str,
        model_class_path: str,
        allowed_fields: dict,
        form_class_path: str | None = None,
        instance_pk: str | int | None = None,
        state: GlueFormProxyState | None = None,
        **kwargs
    ) -> Self:
        model_class = cast(
            'type[Model]', get_attr_from_path_string(model_class_path)
        )

        form_class = None
        if form_class_path:
            form_class = cast(
                'type[ModelForm]', get_attr_from_path_string(form_class_path)
            )
        else:
            form_class = modelform_factory(
                model_class,
                fields=list(allowed_fields.keys()),
            )

        model_instance = model_class()
        if instance_pk:
            model_instance = model_class.objects.get(pk=instance_pk)

            if state:
                form = form_class(
                    initial=state.instance_data,
                    instance=model_instance,
                    files=state.files
                )
            else:
                form = form_class(instance=model_instance)

        else:
            form = form_class()

        return cls(
            model_instance=model_instance,
            form_instance=form,
            name=name,
            access=access,
            **kwargs
        )

    @property
    def _custom_contract_data(self) -> dict:
        model_class = self.model_instance.__class__

        contract_data = {
            'fields': self._field_metadata,
            'model_class_path': f'{model_class.__module__}.{model_class.__name__}',
            'pk_field_name': self.model_instance.__class__._meta.pk.name,
        }

        if self.form_class_path:
            contract_data.update({
                'form_class_path': self.form_class_path,
            })

        return contract_data

    def _set_m2m_fields(self, field_data: dict) -> None:
        model_instance = self.model_instance
        model_meta = model_instance._meta

        for field in chain(model_meta.many_to_many, model_meta.private_fields):
            if not hasattr(field, 'save_form_data'):
                continue
            if field.name in field_data:
                field.save_form_data(model_instance, field_data[field.name])

    @action(access=GlueAccess.VIEW)
    def get(self, request: HttpRequest) -> dict:
        return model_to_dict(
            instance=self.model_instance,
            fields=list(self._field_metadata.keys())
        )

    @action(access=GlueAccess.DELETE)
    def delete(self, request: HttpRequest) -> None:
        self.model_instance.delete()

    @transaction.atomic
    @action(access=GlueAccess.CHANGE)
    def save(self, request: HttpRequest) -> None:
        cast('ModelForm', self.form_instance).save()
