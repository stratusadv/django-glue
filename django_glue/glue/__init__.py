from django.utils.module_loading import import_string

from django_glue.glue.base import BaseGlue
from django_glue.glue.model.glue import ModelGlue
from django_glue.conf import settings

__all__ = []

for _, glue_class_path in getattr(settings, 'DJANGO_GLUE_TARGET_CONFIG').items():
    glue_class = import_string(glue_class_path)
    if glue_class:
        __all__.append(glue_class.__name__)