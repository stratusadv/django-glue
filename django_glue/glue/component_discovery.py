from __future__ import annotations

import pkgutil
from importlib import import_module

from django.apps import apps
from django.utils.module_loading import module_has_submodule


def autodiscover_components() -> None:
    for app_config in apps.get_app_configs():
        if not module_has_submodule(app_config.module, 'components'):
            continue
        module_name = f'{app_config.name}.components'
        module = import_module(module_name)
        module_path = getattr(module, '__path__', None)
        if module_path is None:
            continue
        for _, submodule_name, _ in pkgutil.walk_packages(module_path, f'{module_name}.'):
            if any(part.startswith('_') for part in submodule_name.split('.')):
                continue
            import_module(submodule_name)
