from django.db import models
from enum import Enum


class FieldType(str, Enum):
    AUTO_FIELD = models.AutoField.__name__
    BIG_AUTO_FIELD = models.BigAutoField.__class__.__name__
    SMALL_AUTO_FIELD = models.SmallAutoField.__class__.__name__
    BOOLEAN = models.BooleanField.__class__.__name__
    CHAR = models.CharField.__name__
    COMMA_SEPARATED_INTEGER = models.CommaSeparatedIntegerField.__name__
    DATE = models.DateField.__class__.__name__
    DATETIME = models.DateTimeField.__class__.__name__
    DECIMAL = models.DecimalField.__class__.__name__
    DURATION = models.DurationField.__class__.__name__
    EMAIL = models.EmailField.__class__.__name__
    FILE = models.FileField.__class__.__name__
    FILE_PATH = models.FilePathField.__class__.__name__
    FLOAT = models.FloatField.__class__.__name__
    INTEGER = models.IntegerField.__class__.__name__
    BIG_INTEGER = models.BigIntegerField.__class__.__name__
    SMALL_INTEGER = models.SmallIntegerField.__class__.__name__
    IP_ADDRESS = models.IPAddressField.__class__.__name__
    GENERIC_IP_ADDRESS = models.GenericIPAddressField.__class__.__name__
    NULL_BOOLEAN = models.NullBooleanField.__class__.__name__
    POSITIVE_BIG_INTEGER = models.PositiveBigIntegerField.__class__.__name__
    POSITIVE_INTEGER = models.PositiveIntegerField.__class__.__name__
    POSITIVE_SMALL_INTEGER = models.PositiveSmallIntegerField.__class__.__name__
    SLUG = models.SlugField.__class__.__name__
    TEXT = models.TextField.__class__.__name__
    TIME = models.TimeField.__class__.__name__
    URL = models.URLField.__class__.__name__
    UUID = models.UUIDField.__class__.__name__

    def glue_field_class(self) -> 'GlueField':
        from django_glue.form.maps import FIELD_TYPE_TO_GLUE_FIELD
        return FIELD_TYPE_TO_GLUE_FIELD[self]
