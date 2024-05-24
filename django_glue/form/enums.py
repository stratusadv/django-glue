from django.db import models
from enum import Enum


class GlueAttrType(str, Enum):
    HTML = 'html'
    FIELD = 'field'


class FieldType(str, Enum):
    AUTO_FIELD = models.AutoField.__name__
    BIG_AUTO_FIELD = models.BigAutoField.__name__
    SMALL_AUTO_FIELD = models.SmallAutoField.__name__
    BOOLEAN = models.BooleanField.__name__
    CHAR = models.CharField.__name__
    COMMA_SEPARATED_INTEGER = models.CommaSeparatedIntegerField.__name__
    DATE = models.DateField.__name__
    DATETIME = models.DateTimeField.__name__
    DECIMAL = models.DecimalField.__name__
    DURATION = models.DurationField.__name__
    EMAIL = models.EmailField.__name__
    FILE = models.FileField.__name__
    FILE_PATH = models.FilePathField.__name__
    FLOAT = models.FloatField.__name__
    INTEGER = models.IntegerField.__name__
    BIG_INTEGER = models.BigIntegerField.__name__
    SMALL_INTEGER = models.SmallIntegerField.__name__
    IP_ADDRESS = models.IPAddressField.__name__
    GENERIC_IP_ADDRESS = models.GenericIPAddressField.__name__
    NULL_BOOLEAN = models.NullBooleanField.__name__
    POSITIVE_BIG_INTEGER = models.PositiveBigIntegerField.__name__
    POSITIVE_INTEGER = models.PositiveIntegerField.__name__
    POSITIVE_SMALL_INTEGER = models.PositiveSmallIntegerField.__name__
    SLUG = models.SlugField.__name__
    TEXT = models.TextField.__name__
    TIME = models.TimeField.__name__
    URL = models.URLField.__name__
    UUID = models.UUIDField.__name__
