from django_glue.form.enums import FieldTypes
from django_glue.form import factories


FIELD_TYPE_TO_FACTORY_METHOD = {
    FieldTypes.CHAR_FIELD: factories.GlueCharFieldFactory
}