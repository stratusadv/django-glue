from django_glue.form.enums import FieldType
from django_glue.form import fields


FIELD_TYPE_TO_GLUE_FIELD = {
    FieldType.CHAR: fields.GlueCharField
}
