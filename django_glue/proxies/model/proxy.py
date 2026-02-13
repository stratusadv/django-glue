from __future__ import annotations

import sys
from collections.abc import Sequence
from functools import cached_property
from typing import Any

from django.apps import apps
from django.db.models import Model, ForeignObjectRel, Field
from django.forms import model_to_dict

from django_glue.access.access import GlueAccess
from django_glue.proxies.proxy import BaseGlueProxy
from django_glue.proxies.decorators import action


class GlueModelProxy(BaseGlueProxy):
    subject_type = Model

    def __init__(
        self,
        target: Model,
        unique_name: str,
        fields: Sequence = (),
        exclude: Sequence = (),
        access: str = GlueAccess.VIEW,
        **kwargs
    ):
        super().__init__(target, unique_name, access)

        self.target_pk = target.pk
        self.model_class = target.__class__
        self.app_label = target._meta.app_label
        self.fields = fields
        self.exclude = exclude

    @classmethod
    def from_proxy_registry_data(
        cls,
        target_pk: int | str | None,
        model_class: str,
        app_label: str,
        **kwargs
    ) -> GlueModelProxy:
        model_class = apps.get_model(app_label=app_label, model_name=model_class)

        if target_pk:
            target = model_class.objects.get(pk=target_pk)
        else:
            target = model_class()

        return cls(
            target=target,
            **kwargs
        )

    def _build_session_data(self) -> dict:
        return {
            'model_class': self.model_class.__name__,
            'app_label': self.app_label,
            'target_pk': self.target_pk,
        }

    def _build_context_data(self) -> dict:
        return {
            'fields': self._included_fields,
        }

    @cached_property
    def _included_fields(self) -> dict[str, Any]:
        deconstructed_fields = [
            field.deconstruct()
            for field in self.model_class._meta.get_fields()
            if (
                not isinstance(field, ForeignObjectRel) and
                not field.__class__.__name__ == 'GenericRelation'
            )
        ]

        return {
            field_name: {
                'type': field_type,
                **{
                    opt_name: opt_value
                    for opt_name, opt_value in field_options.items()
                    if opt_name not in ['default']
                }
            }
            for field_name, field_type, _, field_options in deconstructed_fields
        }

    @property
    def target_instance(self):
        if self.target_pk:
            return self.model_class.objects.get(pk=self.target_pk)
        else:
            return self.model_class()

    @action(access=GlueAccess.VIEW)
    def get(self):
        return model_to_dict(
            instance=self.target_instance,
            fields=self._included_fields
        )

    @action(access=GlueAccess.CHANGE)
    def save(self, payload: dict):
        instance = self.target_instance

        for field_name, field_data in payload.items():
            if field_name in self._included_fields:
                setattr(instance, field_name, field_data)

        instance.save()

        return model_to_dict(
            instance=instance,
            fields=self._included_fields
        )

    @action(access=GlueAccess.DELETE)
    def delete(self):
        self.target_instance.delete()
