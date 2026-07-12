from __future__ import annotations

import json
from typing import TYPE_CHECKING

from django_glue.proxies.form.state import GlueFormProxyState
from django_glue.proxies.policy import ProxyPolicySubjectDetails
from django_glue.resolver.attribute_event.encoders import BoundAttributeDataJSONEncoder
from django.forms.models import ModelMultipleChoiceField
from django.forms import modelform_factory
from django_glue.utils import get_attr_from_path_string

if TYPE_CHECKING:
    from django.db.models import Model
    from django.forms.models import ModelForm
    from django_glue.resolver.attribute_event.schemas import BoundProxyAttributeEvent


class GlueModelInstanceProxyState(GlueFormProxyState):
    """State for a model instance proxy — holds the Django model and form instances."""

    namespace = 'model'

    def __init__(self, model: Model, form: ModelForm) -> None:
        super().__init__(form)
        self.model = model

    def serialize(self) -> dict:
        from django.forms import model_to_dict  # noqa: PLC0415
        from django.db.models.fields.files import FieldFile  # noqa: PLC0415

        instance_data = model_to_dict(
            instance=self.model,
            fields=[f for f in self.form.fields if f in self.form.fields],
        )
        
        # Serialize FieldFile objects (e.g., ImageFieldFile) as browser-friendly
        # metadata so file previews and current-file labels survive save responses.
        for key, value in instance_data.items():
            if isinstance(value, FieldFile):
                instance_data[key] = {
                    'name': value.name,
                    'size': value.size,
                    'url': value.url,
                } if value else None
            elif isinstance(self.form.fields.get(key), ModelMultipleChoiceField):
                field = self.form.fields[key]
                items = []
                for item in value:
                    if hasattr(item, 'pk'):
                        items.append({'pk': item.pk, '__str__': str(item)})
                    else:
                        related_obj = field.queryset.model.objects.get(pk=item)
                        items.append({'pk': related_obj.pk, '__str__': str(related_obj)})
                instance_data[key] = items

        data = json.loads(json.dumps(
            {
                'namespace': self.namespace,
                'instance_data': instance_data,
                'errors': dict(self.form.errors),
            }, 
            cls=BoundAttributeDataJSONEncoder)
        )

        return data
    
    @classmethod
    def _get_form_class_from_policy_details(cls, policy_details: ProxyPolicySubjectDetails):
        subject_details = policy_details
        model_class = get_attr_from_path_string(subject_details.model_class_path)

        if subject_details.form_class_path:
            form_class = get_attr_from_path_string(subject_details.form_class_path)
        else:
            form_class = modelform_factory(
                model_class,
                fields=list(subject_details.included_fields.keys()),
            )

        return form_class

    @classmethod
    def deserialize(cls, event: BoundProxyAttributeEvent) -> GlueModelInstanceProxyState:
        form = cls._build_form_instance_from_event(event)
        return cls(model=form.instance, form=form)
