from __future__ import annotations

from django.apps import apps
from django.db.models import Model
from django.forms import model_to_dict

from django_glue.access.access import GlueAccess
from django_glue.data_transfer_objects import GlueActionRequestData
from django_glue.exceptions import GlueModelInstanceNotFoundError
from django_glue.proxies.model.base import GlueModelProxyBase
from django_glue.proxies.decorators import action


class GlueModelProxy(GlueModelProxyBase):
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
    def from_action_request_data(
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

        return super().from_action_request_data(
            target=target,
            **kwargs
        )

    def get_model_class(self):
        return self.target.__class__

    def _get_model_instance(self) -> Model:
        return self.target

    def _build_context_data(self) -> dict:
        return {
            'model_class': self.get_model_class().__name__,
            'app_label': self.app_label,
            'target_pk': self.target_pk,
        } | super()._build_context_data()

    @action(access=GlueAccess.VIEW)
    def get(self, action_data: GlueActionRequestData):
        return model_to_dict(
            instance=self._get_model_instance(),
            fields=self._form_field_definitions,
        )

    @action(access=GlueAccess.DELETE)
    def delete(self, action_data: GlueActionRequestData):
        self._get_model_instance().delete()
