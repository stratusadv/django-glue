from __future__ import annotations

import importlib
import pkgutil
import sys
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any

from django.apps import apps
from django.conf import settings as django_settings
from django.core.checks import Error

from django_glue.exceptions import GlueComponentRegistrationError

if TYPE_CHECKING:
    from django_glue.glue.components.component import Component


def _snake_to_pascal(name: str) -> str:
    return ''.join(part.capitalize() for part in name.split('_') if part)


def _candidate_class_names(leaf: str) -> list[str]:
    pascal = _snake_to_pascal(leaf)
    return [f'{pascal}Component', pascal]


def _component_tag_parts(tag_name: str) -> tuple[str, str]:
    directory, _, leaf = tag_name.rpartition('/')
    return directory, leaf


def _has_components_module(location: Path) -> bool:
    return (location / 'components.py').is_file() or (location / 'components').is_dir()


def _import_name_for(target: Path) -> str | None:
    """
    The module's natural dotted import name, from its position relative to
    the closest ``sys.path`` ancestor.

    A ``DIRS`` entry only supplies the lookup base for the tag's directory;
    it does not dictate how the module is imported. A component keeps whatever
    identity the project already imports it under.
    """
    resolved = target.resolve()
    best_depth = -1
    best_parts: tuple[str, ...] | None = None
    for entry in sys.path:
        if not entry:
            continue
        try:
            relative = resolved.relative_to(Path(entry).resolve())
        except ValueError:
            continue
        depth = len(Path(entry).resolve().parts)
        if relative.parts and depth > best_depth:
            best_depth, best_parts = depth, relative.parts
    if best_parts is None:
        return None
    return '.'.join(best_parts)


def _components_module_names(tag_name: str, directory: str) -> Iterator[str]:
    """
    The dotted name of each ``components`` module the tag's directory names, in
    search order: under every ``DIRS`` entry, then inside the installed apps
    when ``APP_DIRS`` is on. A location with no ``components`` module is
    skipped, and one module may be named more than once.
    """
    configured = getattr(django_settings, 'DJANGO_GLUE_COMPONENTS', None) or {}

    for entry in configured.get('DIRS', [django_settings.BASE_DIR]):
        location = Path(entry) / directory
        if not _has_components_module(location):
            continue
        import_name = _import_name_for(location / 'components')
        if import_name is None:
            raise GlueComponentRegistrationError(
                f'Cannot resolve component {tag_name!r}: '
                f'{location / "components"} is not under a sys.path entry.'
            )
        yield import_name

    if not directory or not configured.get('APP_DIRS', True):
        return
    # The tag's directory read as a package path, searched only when it is an
    # installed app or lies inside one.
    package = directory.replace('/', '.')
    for app_config in apps.get_app_configs():
        if package != app_config.name and not package.startswith(f'{app_config.name}.'):
            continue
        inside_app = package.removeprefix(app_config.name).strip('.').replace('.', '/')
        if _has_components_module(Path(app_config.path) / inside_app):
            yield f'{package}.components'


def resolve_component(tag_name: str) -> type[Component]:
    """
    Resolve a snake_case component tag to its class, on demand.

    The tag is an optional directory prefix, then the component name. The last
    segment names the class (``Foo`` or ``FooComponent``); the segments before
    it are a directory, and the component lives in the ``components`` module or
    package that is a child of that directory.

    The directory is looked up the way Django looks up a template: under each
    ``DIRS`` entry of ``DJANGO_GLUE_COMPONENTS``, then inside the installed
    apps. The first location whose ``components`` module defines the class
    wins.
    """
    from django_glue.glue.components.component import Component

    directory, leaf = _component_tag_parts(tag_name)
    candidates = _candidate_class_names(leaf)

    searched: list[str] = []
    for import_name in _components_module_names(tag_name, directory):
        if import_name in searched:
            continue
        searched.append(import_name)
        package = importlib.import_module(import_name)

        modules: list[object] = [package]
        package_path = getattr(package, '__path__', None)
        if package_path is not None:
            for _, submodule_name, _ in pkgutil.walk_packages(package_path, f'{import_name}.'):
                if any(part.startswith('_') for part in submodule_name.split('.')):
                    continue
                modules.append(importlib.import_module(submodule_name))

        for module in modules:
            for candidate in candidates:
                cls = getattr(module, candidate, None)
                if isinstance(cls, type) and issubclass(cls, Component):
                    return cls

    if not searched:
        raise GlueComponentRegistrationError(
            f'Cannot resolve component {tag_name!r}: searched no components module. '
            f'No DJANGO_GLUE_COMPONENTS DIRS entry or installed app has one at {directory!r}.'
        )
    raise GlueComponentRegistrationError(
        f'Cannot resolve component {tag_name!r}: no class named {candidates[0]!r} or '
        f'{candidates[1]!r} in {", ".join(repr(name) for name in searched)}.'
    )


def check_components_setting(app_configs: Any = None, **kwargs: Any) -> list[Error]:
    _ = app_configs, kwargs
    errors: list[Error] = []

    removed_root = getattr(django_settings, 'DJANGO_GLUE_COMPONENTS_ROOT', None)
    if removed_root is not None:
        errors.append(Error(
            'DJANGO_GLUE_COMPONENTS_ROOT is no longer read.',
            hint=f"Replace it with DJANGO_GLUE_COMPONENTS = {{'DIRS': [{str(removed_root)!r}]}}.",
            id='django_glue.E004',
        ))

    configured = getattr(django_settings, 'DJANGO_GLUE_COMPONENTS', None)
    if configured is None:
        return errors

    problem = None
    if not isinstance(configured, Mapping):
        problem = 'It must be a mapping.'
    elif unknown_keys := sorted(set(configured) - {'DIRS', 'APP_DIRS'}):
        problem = f'It has unknown keys: {", ".join(repr(key) for key in unknown_keys)}.'
    elif not isinstance(configured.get('DIRS', []), (list, tuple)):
        problem = "'DIRS' must be a list or tuple of directories."
    elif not isinstance(configured.get('APP_DIRS', True), bool):
        problem = "'APP_DIRS' must be a boolean."
    if problem is not None:
        errors.append(Error(
            f'DJANGO_GLUE_COMPONENTS is malformed. {problem}',
            hint="Shape it like TEMPLATES: {'DIRS': [BASE_DIR / 'app'], 'APP_DIRS': True}.",
            id='django_glue.E005',
        ))
    return errors
