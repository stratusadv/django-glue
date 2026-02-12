from django.utils.module_loading import import_string

from django_glue.conf import settings


def get_adapter_class_for_target_class(target_class_name: type | str):
    from django_glue.adapters.base import BaseGlueAdapter

    if isinstance(target_class_name, type):
        target_class_name = target_class_name.__name__

    glue_type_config = settings.DJANGO_GLUE_TYPE_CONFIG.get(target_class_name, None)

    if glue_type_config is None:
        raise ValueError(f'Invalid Glue type config. Tried to access registered adapter class for {target_class_name} but no class is registered for it in DJANGO_GLUE_TYPE_CONFIG.')

    adapter_class_path = glue_type_config.get('server', None)

    if adapter_class_path is None:
        raise ValueError(f'Invalid Glue type config. Glue adapter class registered for {target_class_name} does not have a valid python classpath set for "server" DJANGO_GLUE_TYPE_CONFIG.')

    adapter_class = import_string(adapter_class_path)

    if not issubclass(adapter_class, BaseGlueAdapter):
        raise ValueError(f'Invalid Glue target config. Glue adapter class registered for {target_class_name} ({adapter_class.__name__}) does not inherit BaseGlueAdapter.')

    return adapter_class
