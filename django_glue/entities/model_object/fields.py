from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Type

from django.db.models import Model
from django.utils import timezone

from django_glue.form.utils import glue_field_attr_from_model_field
from django_glue.form.html_attrs import GlueFieldAttrs


def field_name_included(name, fields, exclude):
    included = False
    if name not in exclude or exclude[0] == '__none__':
        if name in fields or fields[0] == '__all__':
            included = True

    return included


@dataclass
class GlueModelField:
    name: str
    type: str
    value: Any
    field_attrs: GlueFieldAttrs

    def to_dict(self) -> dict:
        # Todo: Create a more extendable way to format values.
        formatted_value = self.value

        if self.value is not None:
            if self.type == 'DateTimeField':
                try:
                    formatted_value = timezone.localtime(self.value).strftime('%Y-%m-%dT%H:%M')
                except Exception:
                    formatted_value = self.value.strftime('%Y-%m-%dT%H:%M')
            elif self.type == 'DateField':
                try:
                    formatted_value = timezone.localdate(self.value).strftime('%Y-%m-%d')
                except Exception:
                    formatted_value = self.value.strftime('%Y-%m-%d')

        return {
            'name': self.name,
            'value': formatted_value,
            'field_attrs': self.field_attrs.to_dict(),
        }


@dataclass
class GlueModelFields:
    fields: list[GlueModelField] = field(default_factory=list)

    def __iter__(self):
        return self.fields.__iter__()

    def to_dict(self):
        return {field.name: field.to_dict() for field in self.fields}


def model_object_fields_from_model(
        model: Type[Model],
        included_fields: tuple,
        excluded_fields: tuple
) -> GlueModelFields:
    fields = []

    for model_field in model._meta.fields:
        if field_name_included(model_field.name, included_fields, excluded_fields):
            fields.append(GlueModelField(
                name=model_field.name,
                type=model_field.get_internal_type(),
                value=None,
                field_attrs=glue_field_attr_from_model_field(model_field)
            ))

    return GlueModelFields(fields=fields)
