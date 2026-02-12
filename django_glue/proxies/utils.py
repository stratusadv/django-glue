from django.utils.module_loading import import_string

from django_glue.conf import settings


# TODO: Clean up the error handling here
def get_proxy_class_for_target_class(target_class_name: type | str):
    from django_glue.proxies.proxy import BaseGlueProxy

    if isinstance(target_class_name, type):
        target_class_name = target_class_name.__name__

    glue_type_config = settings.DJANGO_GLUE_TYPE_CONFIG.get(target_class_name, None)

    if glue_type_config is None:
        raise ValueError(f'Invalid Glue type config. No config found for class for {target_class_name} in DJANGO_GLUE_TYPE_CONFIG.')

    proxy_class_path = glue_type_config['proxy_classes'].get('server', None)

    if proxy_class_path is None:
        raise ValueError(f'Invalid Glue type config. {target_class_name} does not have a valid python classpath set for "proxies.server" in DJANGO_GLUE_TYPE_CONFIG.')

    proxy_class = import_string(proxy_class_path)

    if not issubclass(proxy_class, BaseGlueProxy):
        raise ValueError(f'Invalid Glue target config. Glue proxy class registered for {target_class_name} ({proxy_class.__name__}) does not inherit BaseGlueProxy.')

    return proxy_class
