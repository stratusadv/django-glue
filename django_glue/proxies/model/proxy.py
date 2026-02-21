from __future__ import annotations

from django.apps import apps
from django.db.models import Model
from django.forms import model_to_dict

from django_glue.access.access import GlueAccess
from django_glue.exceptions import GlueModelInstanceNotFoundError
from django_glue.proxies.mixins import GlueProxyFieldsMixin
from django_glue.proxies.decorators import action


class GlueModelProxy(GlueProxyFieldsMixin):
    _subject_type = Model

    def __init__(
        self,
        target: Model,
        **kwargs
    ):
        super().__init__(target=target, **kwargs)

        self.target_pk = target.pk
        self.app_label = target._meta.app_label

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
            try:
                target = model_class.objects.get(pk=target_pk)
            except model_class.DoesNotExist:
                raise GlueModelInstanceNotFoundError(
                    model_name=model_class.__name__,
                    pk=target_pk
                )
        else:
            target = model_class()

        return cls(
            target=target,
            **kwargs
        )

    def get_model_class(self):
        return self.target.__class__

    def _build_session_data(self) -> dict:
        return {
            'model_class': self.get_model_class().__name__,
            'app_label': self.app_label,
            'target_pk': self.target_pk,
        }

    def _build_context_data(self) -> dict:
        return {
            'fields': self._included_fields,
        }

    @property
    def target_instance(self):
        model_class = self.get_model_class()

        if self.target_pk:
            try:
                return model_class.objects.get(pk=self.target_pk)
            except model_class.DoesNotExist:
                raise GlueModelInstanceNotFoundError(
                    model_name=model_class.__name__,
                    pk=self.target_pk
                )
        else:
            return model_class()

    @action(access=GlueAccess.VIEW)
    def get(self):
        return model_to_dict(
            instance=self.target_instance,
            fields=self._included_fields,

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
