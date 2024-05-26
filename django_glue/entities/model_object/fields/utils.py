import logging
from dataclasses import field

from django.db.models import Model

from django_glue.entities.model_object.fields.entities import GlueModelField


def field_name_included(name, fields, exclude):
    included = False
    if name not in exclude or exclude[0] == '__none__':
        if name in fields or fields[0] == '__all__':
            included = True

    return included


def get_field_value_from_model_object(model_object: Model, field: GlueModelField):
    not_implemented = ['ForeignKey', 'BinaryField', 'OnetoOneField']
    if field.type in not_implemented:
        logging.error('Cannot glue relational model fields.')
        return None
    else:
        return getattr(model_object, field.name)
