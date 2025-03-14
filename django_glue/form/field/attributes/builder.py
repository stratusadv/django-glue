from django.db import models

from django_glue.form.field.attributes.attributes import FieldAttributes
from django_glue.form.field.attributes.maps import FIELD_TYPE_TO_FIELD_ATTRIBUTE_FACTORY_MAP


def field_attr_from_model_field(model_field: models.Field) -> FieldAttributes:
    try:
        factory = FIELD_TYPE_TO_FIELD_ATTRIBUTE_FACTORY_MAP[model_field.__class__.__name__]
    except KeyError:
        factory = FIELD_TYPE_TO_FIELD_ATTRIBUTE_FACTORY_MAP[models.CharField.__name__]

    return factory(model_field).factory_method()
