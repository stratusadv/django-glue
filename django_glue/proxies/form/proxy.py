from __future__ import annotations

from django.forms import BaseForm

from django_glue.access.access import GlueAccess
from django_glue.proxies.proxy import BaseGlueProxy
from django_glue.proxies.decorators import action


class GlueFormProxy(BaseGlueProxy):
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
        module_path, class_name = form_class_path.rsplit('.', 1)
        import importlib
        module = importlib.import_module(module_path)
        form_class = getattr(module, class_name)

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

    def _build_context_data(self) -> dict:
        context_data = {
            'form_class_path': f'{self.form_module}.{self.form_class_name}',
            'fields': self._get_field_definitions(),
            'initial': self._get_initial_values(),
        } | super()._build_context_data()

        # For ModelForm, store the instance pk
        if hasattr(self.target,'instance') and self.target.instance and self.target.instance.pk:
            context_data['instance_pk'] = self.target.instance.pk

        return context_data

    def _get_field_definitions(self) -> dict:
        """Extract field metadata for frontend rendering."""
        fields = {}
        for name, field in self.target.fields.items():
            field_def = {
                'type': field.__class__.__name__,
                'required': field.required,
                'label': str(field.label) if field.label else name,
                'help_text': str(field.help_text) if field.help_text else '',
                'widget': field.widget.__class__.__name__,
            }
            if hasattr(field, 'choices') and field.choices:
                # Convert choices to simple (value, label) tuples for JSON serialization
                # This handles ModelChoiceField which has ModelChoiceIteratorValue objects
                field_def['choices'] = [
                    (str(value), str(label)) for value, label in field.choices
                ]
            if hasattr(field, 'max_length') and field.max_length:
                field_def['max_length'] = field.max_length
            if hasattr(field, 'min_length') and field.min_length:
                field_def['min_length'] = field.min_length
            fields[name] = field_def
        return fields

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

    def _serialize_errors(self, errors) -> dict:
        """Convert Django ErrorDict to JSON-serializable dict."""
        return {field: list(error_list) for field, error_list in errors.items()}

    @action(access=GlueAccess.VIEW)
    def get(self):
        """Return form field definitions and current values."""
        return {
            'fields': self._get_field_definitions(),
            'values': self._get_initial_values(),
            'errors': {},
        }

    @action(access=GlueAccess.CHANGE)
    def validate(self, payload: dict):
        """Validate form data without saving."""
        instance = getattr(self.target, 'instance', None)
        if instance and instance.pk:
            form = self.target.__class__(data=payload, instance=instance)
        else:
            form = self.target.__class__(data=payload)

        is_valid = form.is_valid()
        return {
            'is_valid': is_valid,
            'errors': self._serialize_errors(form.errors),
            'cleaned_data': form.cleaned_data if is_valid else {},
        }

    @action(access=GlueAccess.CHANGE)
    def submit(self, payload: dict):
        """Submit and validate form, saving if ModelForm."""
        instance = getattr(self.target, 'instance', None)
        if instance and instance.pk:
            form = self.target.__class__(data=payload, instance=instance)
        else:
            form = self.target.__class__(data=payload)

        if form.is_valid():
            # For ModelForm, save the instance
            if hasattr(form, 'save'):
                saved_instance = form.save()
                return {
                    'success': True,
                    'errors': {},
                    'data': {'id': saved_instance.pk} if hasattr(saved_instance, 'pk') else {},
                }
            return {
                'success': True,
                'errors': {},
                'data': form.cleaned_data,
            }

        return {
            'success': False,
            'errors': self._serialize_errors(form.errors),
            'data': {},
        }
