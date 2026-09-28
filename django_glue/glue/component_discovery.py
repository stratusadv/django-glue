from __future__ import annotations

import importlib
import pkgutil
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from django.conf import settings as django_settings

from django_glue.exceptions import GlueComponentRegistrationError

if TYPE_CHECKING:
    from django_glue.glue.component import Component


def _components_root() -> Path:
    configured = getattr(django_settings, 'DJANGO_GLUE_COMPONENTS_ROOT', None)
    return Path(configured) if configured is not None else Path(django_settings.BASE_DIR)


def _snake_to_pascal(name: str) -> str:
    return ''.join(part.capitalize() for part in name.split('_') if part)


def _candidate_class_names(leaf: str) -> list[str]:
    pascal = _snake_to_pascal(leaf)
    return [f'{pascal}Component', pascal]


def _component_tag_parts(tag_name: str) -> tuple[str, str]:
    directory, _, leaf = tag_name.rpartition('/')
    return directory, leaf


def _import_name_for(target: Path) -> str | None:
    """The module's natural dotted import name, from its position relative to
    the closest ``sys.path`` ancestor.

    The components root only supplies the lookup base for the tag's directory;
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


def resolve_component(tag_name: str) -> type[Component]:
    """Resolve a snake_case component tag to its class, on demand.

    The tag is a path relative to the components root: an optional directory
    prefix, then the component name. The last segment names the class (``Foo``
    or ``FooComponent``); the segments before it are a directory, and the
    component lives in the ``components`` module or package that is a child of
    that directory.
    """
    from django_glue.glue.component import Component

    directory, leaf = _component_tag_parts(tag_name)
    candidates = _candidate_class_names(leaf)
    components_path = _components_root() / (
        f'{directory}/components' if directory else 'components'
    )
    import_name = _import_name_for(components_path)
    if import_name is None:
        raise GlueComponentRegistrationError(
            f'Cannot resolve component {tag_name!r}: '
            f'{components_path} is not under a sys.path entry.'
        )
    try:
        package = importlib.import_module(import_name)
    except ModuleNotFoundError as error:
        raise GlueComponentRegistrationError(
            f'Cannot resolve component {tag_name!r}: no components module at {import_name!r}.'
        ) from error

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

    raise GlueComponentRegistrationError(
        f'Cannot resolve component {tag_name!r}: no class named {candidates[0]!r} or '
        f'{candidates[1]!r} in {import_name!r}.'
    )
