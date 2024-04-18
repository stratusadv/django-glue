from django.db import models
from enum import Enum


class FieldTypes(str, Enum):
    BOOLEAN = str(models.BooleanField)
    CHAR_FIELD = str(models.CharField)
