from django.db.models import Field
from django_glue.form.html_attrs import GlueFieldAttrs
from django_glue.form.maps import FIELD_TYPE_TO_GLUE_FIELD


def glue_field_attrs_from_model_field(model_field: Field) -> GlueFieldAttrs:
        glue_field_class = FIELD_TYPE_TO_GLUE_FIELD[model_field.__class__.__name__]
        kwargs = glue_field_class.kwargs_from_model_field(model_field)
        return glue_field_class(**kwargs)

