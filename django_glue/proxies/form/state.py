from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.forms.models import ModelChoiceField, ModelMultipleChoiceField

from django_glue.proxies.policy import ProxyPolicySubjectDetails
from django_glue.proxies.state import BaseProxyState

from django_glue.utils import get_attr_from_path_string

if TYPE_CHECKING:
    from django.forms.forms import BaseForm
    from django_glue.resolver.attribute_event.schemas import BoundProxyAttributeEvent


class GlueFormProxyState(BaseProxyState):
    """State for a form proxy — holds the Django form instance."""

    namespace = 'form'

    def __init__(self, form: BaseForm) -> None:
        self.form = form

    @property
    def target_pk(self) -> str | int | None:
        return self.form.instance.pk if hasattr(self.form, 'instance') else None

    @property
    def errors(self) -> dict:
        if not self.form.is_bound:
            form_class = self.form.__class__
            form_kwargs: dict[str, Any] = {
                'data': self.form.initial,
                'files': self.form.files,
            }
            if hasattr(self.form, 'instance') and self.form.instance is not None:
                form_kwargs['instance'] = self.form.instance
            self.form = form_class(**form_kwargs)
        self.form.is_valid()
        return dict(self.form.errors)

    def serialize(self) -> dict:
        # Use form.data if form is bound (even if empty), otherwise use initial
        instance_data = dict(self.form.data) if self.form.is_bound else self.form.initial
        return {
            'namespace': self.namespace,
            'instance_data': instance_data,
            'errors': dict(self.form.errors),
        }

    @classmethod
    def _get_form_class_from_policy_details(
        cls,
        policy_details: ProxyPolicySubjectDetails
    ) -> type[BaseForm]:
        return get_attr_from_path_string(policy_details.form_class_path)

    @staticmethod
    def _normalize_model_choice_value(field: ModelChoiceField, value: Any) -> Any:
        if value in (None, ''):
            return value

        if isinstance(value, dict):
            pk_name = field.queryset.model._meta.pk.name
            return value.get('pk', value.get(pk_name, value.get('id', value)))

        return value

    @classmethod
    def _normalize_instance_data_for_form(
        cls,
        form_class: type[BaseForm],
        instance_data: dict[str, Any],
    ) -> dict[str, Any]:
        normalized_data = dict(instance_data)

        for field_name, value in normalized_data.items():
            field = form_class.base_fields.get(field_name)

            if isinstance(field, ModelMultipleChoiceField) and isinstance(value, list):
                normalized_data[field_name] = [
                    cls._normalize_model_choice_value(field, item)
                    for item in value
                ]
            elif isinstance(field, ModelChoiceField):
                normalized_data[field_name] = cls._normalize_model_choice_value(field, value)

        return normalized_data

    @classmethod
    def _build_form_instance_from_event(cls, event: BoundProxyAttributeEvent):
        subject_details = event.policy.subject_details
        form_class = cls._get_form_class_from_policy_details(event.policy.subject_details)

        model_form_meta = getattr(form_class, 'Meta', None)
        model_class = getattr(model_form_meta, 'model', None)

        form_kwargs = {'files': event.request.FILES}

        if model_class is not None:
            target_pk = subject_details.target_pk
            if target_pk != 0 and target_pk is not None and model_class is not None:
                model_instance = model_class.objects.get(pk=target_pk)
            else:
                model_instance = model_class()

            form_kwargs.update({'instance': model_instance})

        state_data = event.proxy_state
        if state_data:
            instance_data = state_data.get('instance_data')
            if instance_data:
                form_kwargs.update({
                    'data': cls._normalize_instance_data_for_form(form_class, instance_data),
                })

        return form_class(**form_kwargs)

    @classmethod
    def deserialize(cls, event: BoundProxyAttributeEvent) -> GlueFormProxyState:
        return cls(form=cls._build_form_instance_from_event(event))
