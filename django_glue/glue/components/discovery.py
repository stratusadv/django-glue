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


def _has_components_module(location: Path, nested: tuple[str, ...]) -> bool:
    if nested:
        return (location / 'components').joinpath(*nested).is_dir()
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


def _components_module_names(
    tag_name: str, directory: str, nested: tuple[str, ...],
) -> Iterator[str]:
    """
    The dotted name of each module one reading of the tag names, in search
    order: under every ``DIRS`` entry, then inside the installed apps when
    ``APP_DIRS`` is on. The module is the ``components`` module that is a child
    of ``directory``, or the package at ``nested`` inside it. A location that
    does not have it is skipped, and one module may be named more than once.
    """
    configured = getattr(django_settings, 'DJANGO_GLUE_COMPONENTS', None) or {}

    for entry in configured.get('DIRS', [django_settings.BASE_DIR]):
        location = Path(entry) / directory
        if not _has_components_module(location, nested):
            continue
        import_name = _import_name_for(location / 'components')
        if import_name is None:
            # A misconfigured entry, not a missing component: skipping it would
            # hide the mistake behind whichever location answered instead.
            raise GlueComponentRegistrationError(
                f'Cannot resolve component {tag_name!r}: the DJANGO_GLUE_COMPONENTS DIRS entry '
                f'{str(entry)!r} has a components module at {location / "components"} that cannot '
                'be imported, because no sys.path entry contains it. Put the directory on '
                'sys.path or remove the entry.'
            )
        yield '.'.join((import_name, *nested))

    if not directory or not configured.get('APP_DIRS', True):
        return
    # The tag's directory read as a package path, searched only when it is an
    # installed app or lies inside one.
    package = directory.replace('/', '.')
    for app_config in apps.get_app_configs():
        if package != app_config.name and not package.startswith(f'{app_config.name}.'):
            continue
        inside_app = package.removeprefix(app_config.name).strip('.').replace('.', '/')
        if _has_components_module(Path(app_config.path) / inside_app, nested):
            yield '.'.join((package, 'components', *nested))


def _find_component_class(import_name: str, candidates: list[str]) -> type[Component] | None:
    """
    The candidate class defined in the module's own namespace or, when it is a
    package, in one of its direct modules. A package inside it is not searched:
    its name is part of the tag.
    """
    from django_glue.glue.components.component import Component

    try:
        package = importlib.import_module(import_name)
    except ModuleNotFoundError as error:
        if error.name != import_name:
            raise
        # A directory left beside a ``components.py`` module is not a package
        # inside it.
        return None

    modules: list[object] = [package]
    for module_info in pkgutil.iter_modules(getattr(package, '__path__', ())):
        if module_info.ispkg or module_info.name.startswith('_'):
            continue
        modules.append(importlib.import_module(f'{import_name}.{module_info.name}'))

    for module in modules:
        for candidate in candidates:
            cls = getattr(module, candidate, None)
            if isinstance(cls, type) and issubclass(cls, Component):
                return cls
    return None


def resolve_component(tag_name: str) -> type[Component]:
    """
    Resolve a snake_case component tag to its class, on demand.

    The tag is an optional directory prefix, then the component name. The last
    segment names the class (``Foo`` or ``FooComponent``). The segments before
    it are a directory holding a ``components`` module or package, then any
    directories inside that package: ``app/cards/foo`` reads as the
    ``components`` module of ``app/cards`` and as ``app/components/cards``.

    Each reading is looked up the way Django looks up a template: under each
    ``DIRS`` entry of ``DJANGO_GLUE_COMPONENTS``, then inside the installed
    apps, and the first location that defines the class wins. A tag that two
    readings resolve to different classes is ambiguous and is refused.
    """
    *directories, leaf = tag_name.split('/')
    candidates = _candidate_class_names(leaf)

    searched: list[str] = []
    resolved: list[type[Component]] = []
    for depth in range(len(directories), -1, -1):
        directory, nested = '/'.join(directories[:depth]), tuple(directories[depth:])
        for import_name in _components_module_names(tag_name, directory, nested):
            if import_name in searched:
                continue
            searched.append(import_name)
            cls = _find_component_class(import_name, candidates)
            if cls is not None:
                if cls not in resolved:
                    resolved.append(cls)
                break

    if len(resolved) > 1:
        raise GlueComponentRegistrationError(
            f'Component tag {tag_name!r} is ambiguous: it names '
            f'{" and ".join(f"{cls.__module__}.{cls.__qualname__}" for cls in resolved)}. '
            'Rename one, or stamp the one you mean by its dotted path.'
        )
    if resolved:
        return resolved[0]
    if not searched:
        raise GlueComponentRegistrationError(
            f'Cannot resolve component {tag_name!r}: searched no components module. '
            f'No DJANGO_GLUE_COMPONENTS DIRS entry or installed app has one for {tag_name!r}.'
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
