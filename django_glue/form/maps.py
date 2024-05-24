from django_glue.form.enums import FieldType
from django_glue.form import factories


FIELD_TYPE_TO_GLUE_ATTR_FACTORY = {
    # FieldType.AUTO_FIELD: html_attrs.GlueIntegerFieldAttr,
    # FieldType.BIG_AUTO_FIELD: html_attrs.GlueIntegerFieldAttr,
    # FieldType.SMALL_AUTO_FIELD: html_attrs.GlueIntegerFieldAttr,
    # FieldType.BOOLEAN: html_attrs.GlueBooleanFieldAttr,
    FieldType.CHAR: factories.GlueCharAttrFactory,
    # FieldType.COMMA_SEPARATED_INTEGER: html_attrs.GlueIntegerFieldAttr,
    # FieldType.DATE: html_attrs.GlueDateFieldAttr,
    # FieldType.DATETIME: html_attrs.GlueDateTimeFieldAttr,
    # FieldType.DECIMAL: html_attrs.GlueDecimalFieldAttr,
    # FieldType.DURATION: html_attrs.GlueIntegerFieldAttr,
    # FieldType.EMAIL: html_attrs.GlueEmailFieldAttr,
    # FieldType.FLOAT: html_attrs.GlueFloatFieldAttr,
    # FieldType.INTEGER: html_attrs.GlueIntegerFieldAttr,
    # FieldType.BIG_INTEGER: html_attrs.GlueIntegerFieldAttr,
    # FieldType.SMALL_INTEGER: html_attrs.GlueIntegerFieldAttr,
    # FieldType.IP_ADDRESS: html_attrs.GlueCharFieldAttr,
    # FieldType.GENERIC_IP_ADDRESS: html_attrs.GlueCharFieldAttr,
    # FieldType.NULL_BOOLEAN: html_attrs.GlueBooleanFieldAttr,
    # FieldType.POSITIVE_BIG_INTEGER: html_attrs.GlueIntegerFieldAttr,
    # FieldType.POSITIVE_INTEGER: html_attrs.GlueIntegerFieldAttr,
    # FieldType.POSITIVE_SMALL_INTEGER: html_attrs.GlueIntegerFieldAttr,
    # FieldType.SLUG: html_attrs.GlueCharFieldAttr,
    FieldType.TEXT: factories.GlueTextAreaAttrFactory,
    # FieldType.TIME: html_attrs.GlueDateTimeFieldAttr,
    # FieldType.URL: html_attrs.GlueCharFieldAttr,
    # FieldType.UUID: html_attrs.GlueCharFieldAttr
}
