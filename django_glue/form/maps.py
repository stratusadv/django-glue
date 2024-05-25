from django_glue.form.enums import FieldType
from django_glue.form import factories


FIELD_TYPE_TO_GLUE_ATTR_FACTORY = {
    FieldType.AUTO_FIELD: factories.GlueIntegerAttrFactory,
    FieldType.BIG_AUTO_FIELD: factories.GlueIntegerAttrFactory,
    FieldType.SMALL_AUTO_FIELD: factories.GlueIntegerAttrFactory,
    FieldType.BOOLEAN: factories.GlueBooleanAttrFactory,
    FieldType.CHAR: factories.GlueCharAttrFactory,
    FieldType.COMMA_SEPARATED_INTEGER: factories.GlueIntegerAttrFactory,  # Now depreciated in django.
    # FieldType.DATE: html_attrs.GlueDateFieldAttr,
    # FieldType.DATETIME: html_attrs.GlueDateTimeFieldAttr,
    FieldType.DECIMAL: factories.GlueDecimalAttrFactory,
    FieldType.DURATION: factories.GlueCharAttrFactory,
    FieldType.EMAIL: factories.GlueCharAttrFactory,
    FieldType.FLOAT: factories.GlueDecimalAttrFactory,
    FieldType.INTEGER: factories.GlueIntegerAttrFactory,
    FieldType.BIG_INTEGER: factories.GlueIntegerAttrFactory,
    FieldType.SMALL_INTEGER: factories.GlueIntegerAttrFactory,
    FieldType.IP_ADDRESS: factories.GlueCharAttrFactory,
    FieldType.GENERIC_IP_ADDRESS: factories.GlueCharAttrFactory,
    # FieldType.NULL_BOOLEAN: html_attrs.GlueBooleanFieldAttr,
    FieldType.POSITIVE_BIG_INTEGER: factories.GlueIntegerAttrFactory,
    FieldType.POSITIVE_INTEGER: factories.GlueIntegerAttrFactory,
    FieldType.POSITIVE_SMALL_INTEGER: factories.GlueIntegerAttrFactory,
    FieldType.SLUG: factories.GlueCharAttrFactory,
    FieldType.TEXT: factories.GlueTextAreaAttrFactory,
    # FieldType.TIME: html_attrs.GlueDateTimeFieldAttr,
    FieldType.URL: factories.GlueCharAttrFactory,
    FieldType.UUID: factories.GlueCharAttrFactory
}
