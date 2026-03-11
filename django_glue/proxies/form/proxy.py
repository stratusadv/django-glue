from __future__ import annotations

from django.forms import BaseForm

from django_glue.access.access import GlueAccess
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

        # For ModelForm, fetch the instance if pk provided
        instance = None
        if instance_pk is not None and hasattr(form_class, '_meta') and hasattr(form_class._meta, 'model'):
            model_class = form_class._meta.model
            try:
                instance = model_class.objects.get(pk=instance_pk)
            except model_class.DoesNotExist:
                pass

        if instance:
            target = form_class(initial=initial, instance=instance)
        else:
            target = form_class(initial=initial)

        return cls(target=target, **kwargs)

    def _get_form_class(self) -> type[BaseForm]:
        """Return the form class for this proxy."""
        return self.target.__class__

    def _get_form_instance(self, data: dict | None = None) -> BaseForm:
        """Create a form instance, optionally bound with data."""
        instance = getattr(self.target, 'instance', None)
        if instance and instance.pk:
            return self._get_form_class()(data=data, instance=instance)
        return self._get_form_class()(data=data)

    def _build_context_data(self) -> dict:
        context_data = {
            'form_class_path': f'{self.form_module}.{self.form_class_name}',
            'fields': self._form_field_definitions,
            'initial': self._get_initial_values(),
        } | super()._build_context_data()

        # For ModelForm, store the instance pk
        if hasattr(self.target, 'instance') and self.target.instance and self.target.instance.pk:
            context_data['instance_pk'] = self.target.instance.pk

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

        # For bound ModelForm, get values from instance
        if hasattr(self.target, 'instance') and self.target.instance and self.target.instance.pk:
            for name in self.target.fields.keys():
                if hasattr(self.target.instance, name):
                    values[name] = getattr(self.target.instance, name)

        return values

    @action(access=GlueAccess.VIEW)
    def get(self):
        """Return form field definitions and current values."""
        return {
            'fields': self._form_field_definitions,
            'values': self._get_initial_values(),
            'errors': {},
        }
