from django_glue.form.field.attributes import factories
from django_glue.form.field.enums import FieldType


FIELD_TYPE_TO_FIELD_ATTRIBUTE_FACTORY_MAP = {
    FieldType.AUTO_FIELD: factories.IntegerAttributeFactory,
    FieldType.BIG_AUTO_FIELD: factories.IntegerAttributeFactory,
    FieldType.SMALL_AUTO_FIELD: factories.IntegerAttributeFactory,
    FieldType.BOOLEAN: factories.BooleanAttributeFactory,
    FieldType.CHAR: factories.CharAttributeFactory,
    FieldType.COMMA_SEPARATED_INTEGER: factories.IntegerAttributeFactory,  # Now depreciated in django.
    FieldType.DATE: factories.DateAttributeFactory,
    FieldType.DATETIME: factories.DateAttributeFactory,
    FieldType.DECIMAL: factories.DecimalAttributeFactory,
    FieldType.DURATION: factories.CharAttributeFactory,
    FieldType.EMAIL: factories.CharAttributeFactory,
    FieldType.FLOAT: factories.DecimalAttributeFactory,
    FieldType.INTEGER: factories.IntegerAttributeFactory,
    FieldType.BIG_INTEGER: factories.IntegerAttributeFactory,
    FieldType.SMALL_INTEGER: factories.IntegerAttributeFactory,
    FieldType.GENERIC_IP_ADDRESS: factories.CharAttributeFactory,
    FieldType.IP_ADDRESS: factories.CharAttributeFactory,
    FieldType.FOREIGN_KEY: factories.IntegerAttributeFactory,
    FieldType.ONE_TO_ONE: factories.IntegerAttributeFactory,
    FieldType.MANY_TO_MANY: factories.CharAttributeFactory,
    FieldType.JSON: factories.TextAreaAttributeFactory,
    FieldType.NULL_BOOLEAN: factories.BooleanAttributeFactory,  # Now depreciated in django
    FieldType.POSITIVE_BIG_INTEGER: factories.IntegerAttributeFactory,
    FieldType.POSITIVE_INTEGER: factories.IntegerAttributeFactory,
    FieldType.POSITIVE_SMALL_INTEGER: factories.IntegerAttributeFactory,
    FieldType.SLUG: factories.CharAttributeFactory,
    FieldType.TEXT: factories.TextAreaAttributeFactory,
    FieldType.TIME: factories.DateAttributeFactory,
    FieldType.URL: factories.CharAttributeFactory,
    FieldType.UUID: factories.CharAttributeFactory
}
