from __future__ import annotations

from typing import Any, TYPE_CHECKING

from django.db.models import Model
from django.forms.models import ModelForm

from django_glue.access.access import GlueAccess
from django_glue.proxies.model.base import GlueModelProxyBase
from django_glue.proxies.decorators import action

if TYPE_CHECKING:
    from django_glue.resolver.action.schemas import ActionPayloadSchema


class GlueModelFormProxy(GlueModelProxyBase):
    """
    Proxy for Django ModelForm instances.

    Unlike GlueModelProxy which works with model instances directly,
    GlueModelFormProxy works through a specific ModelForm class. This is
    useful when you want form-specific validation, custom fields, or
    custom process() workflows via GlueModelForm.

    Appears under Glue.form on the frontend.
    """

    _subject_type = ModelForm

    def __init__(self, target: ModelForm, **kwargs) -> None:
        # Store form metadata
        self.form_class = target.__class__
        self.form_class_name = target.__class__.__name__
        self.form_module = target.__class__.__module__

        # Get the model instance from the form
        instance = target.instance if target.instance and target.instance.pk else self.form_class._meta.model()
        self._instance_pk = instance.pk if instance.pk else None

        # Store the model instance separately (target remains the form for type checking)
        self._model_instance = instance

        # Pass the form as target, form_class to base
        super().__init__(
            target=target,
            form_class=self.form_class,
            **kwargs
        )

    @classmethod
    def from_action_request_data(
        cls,
        form_class_path: str,
        instance_pk: int | str | None = None,
        **kwargs
    ) -> GlueModelFormProxy:
        """
        Reconstruct a GlueModelFormProxy from action request data.
        """
        from django_glue.utils import get_class_from_path_string

        # Get the form class
        form_class = get_class_from_path_string(form_class_path)

        # Get the model class from the form
        model_cls = form_class._meta.model

        # Get or create the model instance
        if instance_pk:
            instance = model_cls.objects.get(pk=instance_pk)
        else:
            instance = model_cls()

        # Create the form with the instance
        target = form_class(instance=instance)

        return cls(target=target, **kwargs)

    def _register_subject_actions(self):
        """Register actions from the form class."""
        self._register_actions(subject_type=self.form_class, category='form')

    def _get_subject_action_target_by_category(
        self,
        category: str,
        action_payload: ActionPayloadSchema
    ) -> Any:
        """Return the appropriate target for action dispatch."""
        if category == 'form':
            # Get form values from proxy_data (proxy-intrinsic state)
            proxy_data = action_payload.proxy_data or {}
            form_values = proxy_data.get('form_values', {})

            return self._get_form_instance(
                data=form_values or None,
                files=action_payload.file_data
            )
        return None

    def _get_form_instance(self, data: dict | None = None, files: dict | None = None) -> ModelForm:
        """Create a form instance bound to the model instance."""
        if data is not None:
            for field_name, field in self._form_field_definitions.items():
                # Ensure that Multiple choice fields have list values
                if field['type'] in ['ModelMultipleChoiceField', 'MultipleChoiceField']:
                    value = data.get(field_name)
                    if value and not isinstance(value, list):
                        data[field_name] = [value]

            return self.form_class(data=data, files=files, instance=self._get_model_instance())

        return self.form_class(instance=self._get_model_instance())

    def get_model_class(self) -> type[Model]:
        """Return the Django model class associated with this proxy."""
        return self.form_class._meta.model

    def _get_model_instance(self) -> Model:
        """Return the model instance for form binding."""
        if self._instance_pk:
            return self.get_model_class().objects.get(pk=self._instance_pk)
        return self._model_instance

    def _build_context_data(self) -> dict:
        return {
            'form_class_path': f'{self.form_module}.{self.form_class_name}',
            'instance_pk': self._instance_pk,
        } | super()._build_context_data()

    def _get_initial_values(self) -> dict:
        """Get initial form values from the model instance."""
        values = {}
        instance = self._get_model_instance()

        # Get values from model instance
        if instance.pk:
            for name in self.form_class().fields.keys():
                if hasattr(instance, name):
                    value = getattr(instance, name)
                    # Handle many-to-many fields
                    if hasattr(value, 'all'):
                        values[name] = list(value.values_list('pk', flat=True))
                    else:
                        values[name] = value

        # Override with form's initial values if set
        form = self.form_class(instance=instance)
        for name, field in form.fields.items():
            if name in form.initial:
                values[name] = form.initial[name]
            elif name not in values and field.initial is not None:
                values[name] = field.initial

        return values

    @action(access=GlueAccess.VIEW)
    def get(self, request) -> dict:
        """Return form field definitions and current values."""
        return {
            'fields': self._form_field_definitions,
            'values': self._get_initial_values(),
            'errors': {},
        }

