from __future__ import annotations

from django.db.models import Model
from django.forms import BaseForm

from django_glue.access.access import GlueAccess
from django_glue.data_transfer_objects import GlueActionRequestData
from django_glue.proxies.proxy import BaseGlueProxy
from django_glue.proxies.decorators import action
from django_glue.proxies.form.mixin import GlueFormProxyMixin
from django_glue.utils import get_class_from_path_string


class GlueFormProxy(GlueFormProxyMixin, BaseGlueProxy):
    """Proxy for Django Form instances."""

    _subject_type = BaseForm

    def __init__(self, target: BaseForm, **kwargs):
        super().__init__(target=target, **kwargs)
        self.form_class_name = target.__class__.__name__
        self.form_module = target.__class__.__module__

    @classmethod
    def from_action_request_data(
        cls,
        form_class_path: str,
        initial: dict,
        instance_pk: int | str | None = None,
        **kwargs
    ) -> GlueFormProxy:
        form_class = get_class_from_path_string(form_class_path)
        target = form_class(initial=initial)
        return cls(target=target, **kwargs)

    def _get_form_class(self) -> type[BaseForm]:
        """Return the form class for this proxy."""
        return self.target.__class__

    def _build_context_data(self) -> dict:
        context_data = {
            'form_class_path': f'{self.form_module}.{self.form_class_name}',
            'fields': self._form_field_definitions,
            'initial': self._get_initial_values(),
        } | super()._build_context_data()

        return context_data

    def _get_initial_values(self) -> dict:
        """Get initial form values."""
        values = {}
        for name, field in self.target.fields.items():
            # Check form's initial dict first, then field's initial
            if name in self.target.initial:
                values[name] = self.target.initial[name]
            elif field.initial is not None:
                values[name] = field.initial
            else:
                values[name] = None

        return values

    @action(access=GlueAccess.VIEW)
    def get(self, action_data: GlueActionRequestData):
        """Return form field definitions and current values."""
        return {
            'fields': self._form_field_definitions,
            'values': self._get_initial_values(),
            'errors': {},
        }
