from typing import Type

from django.db.models import Model

from django_glue.form.field.factories import FormFieldFactory
from django_glue.glue.model_object.fields.glue import ModelFieldsGlue, ModelFieldGlue, ModelFieldMetaGlue
from django_glue.glue.model_object.fields.utils import field_name_included


def model_object_fields_glue_from_model(
        model: Type[Model],
        included_fields: tuple,
        excluded_fields: tuple
) -> ModelFieldsGlue:
    fields = []

    for model_field in model._meta.fields:
        if field_name_included(model_field.name, included_fields, excluded_fields):

            _meta = ModelFieldMetaGlue(
                type=model_field.get_internal_type(),
                name=model_field.name,
                glue_field=FormFieldFactory(model_field).factory_method()
            )

            glue_model_field = ModelFieldGlue(
                name=model_field.name,
                value=None,
                _meta=_meta
            )

            fields.append(glue_model_field)

    return ModelFieldsGlue(fields=fields)
