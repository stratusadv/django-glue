from django_glue.form.enums import FieldType
from django_glue.form import factories


FIELD_TYPE_TO_GLUE_ATTR_FACTORY = {
    FieldType.AUTO_FIELD: factories.GlueIntegerAttrFactory,
    FieldType.BIG_AUTO_FIELD: factories.GlueIntegerAttrFactory,
    FieldType.SMALL_AUTO_FIELD: factories.GlueIntegerAttrFactory,
    FieldType.BOOLEAN: factories.GlueBooleanAttrFactory,
    FieldType.CHAR: factories.GlueCharAttrFactory,
    FieldType.COMMA_SEPARATED_INTEGER: factories.GlueIntegerAttrFactory,  # Now depreciated in django.
    FieldType.DATE: factories.GlueDateAttrFactory,
    FieldType.DATETIME: factories.GlueDateAttrFactory,
    FieldType.DECIMAL: factories.GlueDecimalAttrFactory,
    FieldType.DURATION: factories.GlueCharAttrFactory,
    FieldType.EMAIL: factories.GlueCharAttrFactory,
    FieldType.FLOAT: factories.GlueDecimalAttrFactory,
    FieldType.INTEGER: factories.GlueIntegerAttrFactory,
    FieldType.BIG_INTEGER: factories.GlueIntegerAttrFactory,
    FieldType.SMALL_INTEGER: factories.GlueIntegerAttrFactory,
    FieldType.GENERIC_IP_ADDRESS: factories.GlueCharAttrFactory,
    FieldType.IP_ADDRESS: factories.GlueCharAttrFactory,
    FieldType.FOREIGN_KEY: factories.GlueIntegerAttrFactory,
    FieldType.ONE_TO_ONE: factories.GlueIntegerAttrFactory,
    FieldType.MANY_TO_MANY: factories.GlueCharAttrFactory,
    FieldType.JSON: factories.GlueTextAreaAttrFactory,
    FieldType.NULL_BOOLEAN: factories.GlueBooleanAttrFactory,  # Now depreciated in django
    FieldType.POSITIVE_BIG_INTEGER: factories.GlueIntegerAttrFactory,
    FieldType.POSITIVE_INTEGER: factories.GlueIntegerAttrFactory,
    FieldType.POSITIVE_SMALL_INTEGER: factories.GlueIntegerAttrFactory,
    FieldType.SLUG: factories.GlueCharAttrFactory,
    FieldType.TEXT: factories.GlueTextAreaAttrFactory,
    FieldType.TIME: factories.GlueDateAttrFactory,
    FieldType.URL: factories.GlueCharAttrFactory,
    FieldType.UUID: factories.GlueCharAttrFactory
}
