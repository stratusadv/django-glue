from __future__ import annotations

import pkgutil
from importlib import import_module

from django.apps import apps
from django.utils.module_loading import module_has_submodule

COMPONENT_MODULE_NAME = 'components'


def autodiscover_components() -> None:
    """Import every component module in each installed app.

    Component classes register through ``__init_subclass__``, which only fires
    when the class is imported. A component nobody imports is invisible to
    reconstruction — and invisible *late*: stamping it works if some view
    happened to import its module, then the next request fails to reconstruct
    it. So discovery has to be exhaustive rather than best-effort.

    This deliberately goes further than Django's ``autodiscover_modules``, which
    imports ``<app>.components`` and stops. When that module is a package, this
    also imports every submodule beneath it, so ``components/day_card.py`` needs
    no re-export from ``components/__init__.py`` to be found.
    """
    for app_config in apps.get_app_configs():
        _import_component_module(app_config.name, app_config.module)


def _import_component_module(app_name: str, app_module: object) -> None:
    if not module_has_submodule(app_module, COMPONENT_MODULE_NAME):
        return

    module_name = f'{app_name}.{COMPONENT_MODULE_NAME}'
    module = import_module(module_name)

    # A plain components.py has no __path__ and is already fully imported.
    module_path = getattr(module, '__path__', None)
    if module_path is None:
        return

    for _, submodule_name, _ in pkgutil.walk_packages(module_path, f'{module_name}.'):
        if any(part.startswith('_') for part in submodule_name.split('.')):
            continue
        import_module(submodule_name)
