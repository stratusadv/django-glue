from django.utils.module_loading import import_string

from django_glue.conf import settings


def get_glue_class_for_target_class(target_class_name: type | str):
    from django_glue.glue.base import BaseGlue

    glue_class_path = settings.DJANGO_GLUE_TARGET_CONFIG.get(target_class_name, None)

    if glue_class_path is None:
        raise ValueError(f'Invalid Glue target config. Tried to access registered glue class for {target_class_name} but no glue class is registered for it in DJANGO_GLUE_TARGET_CONFIG.')

    glue_class = import_string(glue_class_path)

    if not issubclass(glue_class, BaseGlue):
        raise ValueError(f'Invalid Glue target config. Glue class registered for {target_class_name} ({glue_class.__name__}) does not inherit BaseGlue.')

    return glue_class
