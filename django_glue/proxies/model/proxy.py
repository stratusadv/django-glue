"""
Base class for Django Glue model proxies.

Provides field inclusion/exclusion filtering and form-based validation
for proxies that work with Django model fields.
"""

from __future__ import annotations

from abc import ABC
from itertools import chain
from typing import Self, Sequence, cast, TYPE_CHECKING, Any

from django.db import transaction
from django.db.models import Model
from django.forms import model_to_dict, modelform_factory

from django_glue.access.access import GlueAccess
from django_glue.actions.decorators import action
from django_glue.proxies.form.proxy import GlueFormProxy
from django_glue.utils import get_attr_from_path_string
from django.forms.models import ModelForm
from django_glue.proxies.form.state import GlueFormProxyState

if TYPE_CHECKING:
    from django_glue.actions.action import GlueAction
    from django.http import HttpRequest


class BaseGlueModelProxy(GlueFormProxy, ABC):
    _subject_type = Model

    def __init__(
        self,
        model_instance: Model,
        fields: Sequence | dict = (),
        exclude: Sequence[str] = (),
        form_class: type[ModelForm] | None = None,
        form_instance: ModelForm | None = None,
        namespace: str = 'model',
        **kwargs,
    ) -> None:
        self.model_instance = model_instance
        self.namespace = namespace

        self.form_class_path = None
        if form_class:
            if not issubclass(form_class, ModelForm):
                raise ValueError()

            self.form_class_path = f'{form_class.__module__}.{form_class.__name__}'

        # Use provided form_instance, or create one
        if form_instance is None:
            if not form_class:
                if fields == ():
                    fields = [
                        field.name for field in chain(
                            model_instance._meta.fields,
                            model_instance._meta.many_to_many
                        ) if field.editable
                    ]

                form_class = modelform_factory(
                    self.model_instance.__class__,
                    fields=list(set(fields) - set(exclude)),
                )

            form_instance = form_class(instance=self.model_instance)

        super().__init__(form_instance=form_instance, namespace=namespace, **kwargs)

    @classmethod
    def _from_deconstructed_action_request_data(
        cls,
        request: HttpRequest,
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

        model_instance = model_class.objects.get(pk=instance_pk) if instance_pk else model_class()

        if request.FILES:
            # We know we need the form bound here.
            form = form_class(
                data=state.instance_data if state else None,
                instance=model_instance,
                files=request.FILES or None
            )
        else:
            form = form_class(
                initial=state.instance_data if state else None,
                instance=model_instance,
                files=request.FILES or None
            )

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
            'allowed_fields': self._field_metadata,
            'model_class_path': f'{model_class.__module__}.{model_class.__name__}',
            'pk_field_name': self.model_instance.__class__._meta.pk.name,
        }

        if self.form_class_path:
            contract_data.update({
                'form_class_path': self.form_class_path,
            })

        return contract_data

    def get_state(self) -> GlueFormProxyState:
        return GlueFormProxyState(
            instance_data=model_to_dict(
                instance=self.model_instance,
                fields=list(self._field_metadata.keys())
            ),
            errors=self.form_instance.errors,
        )

    def _set_m2m_fields(self, field_data: dict) -> None:
        model_instance = self.model_instance
        model_meta = model_instance._meta

        for field in chain(model_meta.many_to_many, model_meta.private_fields):
            if not hasattr(field, 'save_form_data'):
                continue
            if field.name in field_data:
                field.save_form_data(model_instance, field_data[field.name])

    def _get_action_target(
        self,
        action: GlueAction,
    ) -> Any:
        if issubclass(self.model_instance.__class__, action.target_class):
            return self.model_instance

        return super()._get_action_target(action)

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
        if not self.errors:
            cast('ModelForm', self.form_instance).save()
