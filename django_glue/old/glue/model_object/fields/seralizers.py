from __future__ import annotations

from typing import Any, TYPE_CHECKING

from django.utils import timezone

if TYPE_CHECKING:
    from django_glue.glue.model_object.fields.glue import ModelFieldGlue


def serialize_field_value(model_field_glue: ModelFieldGlue) -> Any:
    formatted_value = model_field_glue.value

    if formatted_value is not None:

        if model_field_glue._meta.type == 'DateTimeField':
            try:
                formatted_value = timezone.localtime(model_field_glue.value).strftime('%Y-%m-%dT%H:%M')
            except Exception:
                formatted_value = model_field_glue.value.strftime('%Y-%m-%dT%H:%M')
        elif model_field_glue._meta.type == 'DateField':
            try:
                formatted_value = timezone.localdate(model_field_glue.value).strftime('%Y-%m-%d')
            except Exception:
                formatted_value = model_field_glue.value.strftime('%Y-%m-%d')

    return formatted_value
