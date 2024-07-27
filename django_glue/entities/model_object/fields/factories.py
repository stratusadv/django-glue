from typing import Type

from django.db.models import Model

from django_glue.entities.model_object.fields.entities import GlueModelFields, GlueModelField, GlueModelFieldMeta
from django_glue.entities.model_object.fields.utils import field_name_included
from django_glue.form.field.factories import GlueFormFieldFactory


def model_object_fields_from_model(
        model: Type[Model],
        included_fields: tuple,
        excluded_fields: tuple
) -> GlueModelFields:
    fields = []

    for model_field in model._meta.fields:
        if field_name_included(model_field.name, included_fields, excluded_fields):

            _meta = GlueModelFieldMeta(
                type=model_field.get_internal_type(),
                name=model_field.name,
                glue_field=GlueFormFieldFactory(model_field).factory_method()
            )

            glue_model_field = GlueModelField(
                name=model_field.name,
                value=None,
                _meta=_meta
            )

            fields.append(glue_model_field)

    return GlueModelFields(fields=fields)
