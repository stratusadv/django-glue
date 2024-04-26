from dataclasses import dataclass, field
from typing import Any

from django.db.models import Model

from django_glue.form.factories import glue_field_attrs_from_model_field
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
    glue_field_attrs: GlueFieldAttrs

    def to_dict(self) -> dict:
        return {
                'name': self.name,
                'value': self.value,
                'html_attr': self.glue_field_attrs.html_attrs
            }


@dataclass
class GlueModelFields:
    fields: list[GlueModelField] = field(default_factory=list)

    def __iter__(self):
        return self.fields.__iter__()

    def to_dict(self):
        return {field.name: field.to_dict() for field in self.fields}


def model_object_fields_from_model(model: Model, included_fields: tuple, excluded_fields: tuple) -> GlueModelFields:
    fields = []

    for model_field in model._meta.fields:
        if field_name_included(model_field.name, included_fields, excluded_fields):
            fields.append(glue_field_attrs_from_model_field(model_field))





            # if hasattr(field, 'get_internal_type'):
            #     # if include_values:
            #     #     field_value = getattr(self.model_object, field.name)
            #     # else:
            #     field_value = None
            #
            #     field_attr = generate_field_attr_dict(field)
            #
            #     if field.many_to_one or field.one_to_one:
            #         field_name = field.name + '_id'
            #     else:
            #         field_name = field.name
            #
            #     fields.append(GlueModelField(
            #         name=field_name,
            #         type=field.get_internal_type(),
            #         value=field_value,
            #         html_attr=field_attr
            #     ))

    return GlueModelFields(fields=fields)
