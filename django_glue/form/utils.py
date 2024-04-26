from django.db.models import Model

from django_glue.form.html_attrs import GlueFormField
from django_glue.form.maps import FIELD_TYPE_TO_FACTORY_METHOD
from django_glue.form.enums import FieldTypes


def find_glue_field_factory(model_field):
    try:
        field_type = FieldTypes(str(model_field))
        return FIELD_TYPE_TO_FACTORY_METHOD[field_type]
    except KeyError:
        raise f'Django Field {model_field} does not exist in Field Type Map.'


def glue_form_field_from_model_field(model_field, model_object: Model) -> GlueFormField:
    glue_factory_class = find_glue_field_factory(model_field)
    glue_factory = glue_factory_class(model_field, model_object)
    return glue_factory.factory_method()
