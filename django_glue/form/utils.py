from django.db import models

from django_glue.form.maps import FIELD_TYPE_TO_GLUE_ATTR_FACTORY
from django_glue.form.html_attrs import GlueFieldAttrs


def glue_field_attr_from_model_field(model_field) -> GlueFieldAttrs:
    try:
        glue_factory = FIELD_TYPE_TO_GLUE_ATTR_FACTORY[str(model_field)]
    except KeyError:
        glue_factory = FIELD_TYPE_TO_GLUE_ATTR_FACTORY[models.CharField.__name__]

    return glue_factory(model_field).factory_method()
