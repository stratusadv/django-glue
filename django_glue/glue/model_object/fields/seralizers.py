from typing import Any

from django.utils import timezone


def serialize_field_value(glue_model_field: 'GlueModelField') -> Any:
    formatted_value = glue_model_field.value

    if formatted_value is not None:

        if glue_model_field._meta.type == 'DateTimeField':
            try:
                formatted_value = timezone.localtime(glue_model_field.value).strftime('%Y-%m-%dT%H:%M')
            except Exception:
                formatted_value = glue_model_field.value.strftime('%Y-%m-%dT%H:%M')
        elif glue_model_field._meta.type == 'DateField':
            try:
                formatted_value = timezone.localdate(glue_model_field.value).strftime('%Y-%m-%d')
            except Exception:
                formatted_value = glue_model_field.value.strftime('%Y-%m-%d')

    return formatted_value
