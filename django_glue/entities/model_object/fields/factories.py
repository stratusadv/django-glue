from typing import Type

from django.db.models import Model

from django_glue.entities.model_object.fields.entities import GlueModelFields, GlueModelField
from django_glue.entities.model_object.fields.utils import field_name_included
from django_glue.form.utils import glue_field_attr_from_model_field


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
