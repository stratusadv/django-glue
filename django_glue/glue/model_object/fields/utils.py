import logging
from dataclasses import field

from django.db.models import Model

from django_glue.glue.model_object.fields.glue import ModelFieldGlue


def field_name_included(name, fields, exclude):
    included = False
    if name not in exclude or exclude[0] == '__none__':
        if name in fields or fields[0] == '__all__':
            included = True

    return included


def get_field_value_from_model_object(model_object: Model, field: ModelFieldGlue):
    relational = ['ForeignKey', 'BinaryField', 'OnetoOneField']
    if field._meta.type in relational:
        return getattr(model_object, f'{field.name}_id')
    else:
        return getattr(model_object, field.name)
