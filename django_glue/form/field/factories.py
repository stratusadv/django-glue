from django.db import models

from django_glue.form.field.attrs.entities import GlueFieldAttrs
from django_glue.form.field.attrs.maps import FIELD_TYPE_TO_GLUE_ATTR_FACTORY


def glue_field_attr_from_model_field(model_field) -> GlueFieldAttrs:
    try:
        glue_factory = FIELD_TYPE_TO_GLUE_ATTR_FACTORY[model_field.__class__.__name__]
    except KeyError:
        glue_factory = FIELD_TYPE_TO_GLUE_ATTR_FACTORY[models.CharField.__name__]

    return glue_factory(model_field).factory_method()
