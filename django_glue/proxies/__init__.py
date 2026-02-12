from django.utils.module_loading import import_string

from django_glue.proxies.proxy import BaseGlueProxy
from django_glue.proxies.model.proxy import GlueModelProxy
from django_glue.conf import settings

__all__ = []

for _, type_config in getattr(settings, 'DJANGO_GLUE_TYPE_CONFIG').items():
    glue_class = import_string(type_config['proxy_classes']['server'])
    if glue_class:
        __all__.append(glue_class.__name__)