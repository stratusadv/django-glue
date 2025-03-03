from typing import Type

from django.db.models import Model

from django_glue.entities.model_object.fields.entities import (
    GlueModelFields, GlueModelField, GlueModelFieldMeta
)
from django_glue.entities.model_object.fields.utils import field_name_included
from django_glue.form.field.entities import GlueAnnotationField
from django_glue.form.field.factories import GlueFormFieldFactory


def model_object_annotations_from_model(
    model: Type[Model],
    model_instance: Model,
    included_fields: tuple,
    excluded_fields: tuple
) -> GlueModelFields:
    fields = []

    instance_source = model_instance

    field_names = {field.name for field in model._meta.fields}
    instance_dict_keys = set(instance_source.__dict__.keys())
    possible_annotated_fields = instance_dict_keys - field_names - {'_state'}

    for attr_name in possible_annotated_fields:
        if attr_name.startswith('_'):
            continue

        value = getattr(instance_source, attr_name)

        if callable(value):
            continue

        if field_name_included(attr_name, included_fields, excluded_fields):
            if not attr_name.endswith('_id'):
                _meta = GlueModelFieldMeta(
                    type='AnnotationField',
                    name=attr_name,
                    glue_field=GlueAnnotationField(attr_name)
                )

                fields.append(
                    GlueModelField(
                        name=attr_name,
                        value=value,
                        _meta=_meta
                    )
                )

    return GlueModelFields(fields=fields)


def model_object_fields_from_model(
    model: Type[Model],
    included_fields: tuple,
    excluded_fields: tuple,
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
