from __future__ import annotations

from abc import ABC
from itertools import chain
from typing import TYPE_CHECKING, Any, Sequence, cast

from django.db import transaction
from django.db.models import Model
from django.forms import model_to_dict, modelform_factory
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

    @classmethod
    def _build_state(
        cls,
        model_instance: Model,
        fields: Sequence | dict = (),
        exclude: Sequence[str] = (),
        form_class: type[ModelForm] | None = None,
    ) -> tuple[GlueModelInstanceProxyState, str | None]:
        form_class_path = None
        if form_class:
            if not issubclass(form_class, ModelForm):
                msg = 'form_class must be a subclass of ModelForm'
                raise ValueError(msg)
            form_class_path = f'{form_class.__module__}.{form_class.__name__}'

        if form_class is None:
            if fields == ():
                fields = [
                    field.name for field in chain(
                        model_instance._meta.fields,
                        model_instance._meta.many_to_many,
                    ) if field.editable
                ]
            form_class = modelform_factory(
                model_instance.__class__,
                fields=list(set(fields) - set(exclude)),
            )

        form_instance = form_class(instance=model_instance)
        return GlueModelInstanceProxyState(model=model_instance, form=form_instance), form_class_path

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
        return model_to_dict(
            instance=self.state.model,
            fields=list(self._field_metadata.keys()),
        )

    @Attribute(access=GlueAccess.DELETE)
    def delete(self, request: HttpRequest) -> None:
        self.state.model.delete()

    @transaction.atomic
    @Attribute(access=GlueAccess.CHANGE)
    def save(self, request: HttpRequest) -> None:
        if not self.state.errors:
            cast('ModelForm', self.state.form).save()
