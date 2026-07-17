from __future__ import annotations

import inspect
from typing import Any, TYPE_CHECKING

from django_glue.access import GlueAccess
from django_glue.glue.attributes.base import BaseGlueAttribute

if TYPE_CHECKING:
    from django_glue.glue.base import BaseGlue


def discover_glue_attributes(owner: BaseGlue) -> dict[str, BaseGlueAttribute]:
    """
    Discover all Glue attributes on a GlueObject.

    Walks the owner and its subjects, finding all @Attribute-decorated
    members and returning them as a flat dict with dotted path names.
    """
    return _discover_glue_attributes(owner=owner, target=owner, path_prefix='', visited=set())


# TODO: this could be optimized - right now does 2 loops through target attrs
def _discover_glue_attributes(
    *,
    owner: BaseGlue,
    target: Any,
    path_prefix: str,
    visited: set[int],
) -> dict[str, BaseGlueAttribute]:
    from django_glue.glue.attributes.callable import CallableAttribute
    from django_glue.glue.attributes.value import ValueAttribute

    instance_id = id(target)
    if instance_id in visited:
        return {}
    visited.add(instance_id)

    attributes: dict[str, BaseGlueAttribute] = {}
    cls = target.__class__

    for attr_name, attr in inspect.getmembers_static(cls):
        access = _get_required_glue_access(cls, attr_name, attr)
        if access is None:
            continue

        name = f'{path_prefix}.{attr_name}' if path_prefix else attr_name

        # TODO: this could use a better name - really means requires client invocation
        is_callable = getattr(attr, 'is_callable', True)
        if is_callable:
            attributes[name] = CallableAttribute(owner=owner, name=name, access=access)
        else:
            attributes[name] = ValueAttribute(owner=owner, name=name, access=access)

    for attr_name, class_attr in inspect.getmembers_static(cls):
        if attr_name.startswith('_') or not hasattr(class_attr, '__get__'):
            continue
        access = _get_required_glue_access(cls, attr_name, class_attr)
        if access is None or getattr(class_attr, 'is_callable', True):
            continue

        try:
            value = getattr(target, attr_name)
        except Exception:  # noqa: S112
            continue

        if value is None or callable(value):
            continue
        if not _class_has_glue_attributes(value.__class__):
            continue

        nested_prefix = f'{path_prefix}.{attr_name}' if path_prefix else attr_name
        attributes.update(
            _discover_glue_attributes(
                owner=owner,
                target=value,
                path_prefix=nested_prefix,
                visited=visited,
            )
        )

    return attributes


def _class_has_glue_attributes(cls: type) -> bool:
    return any(
        _get_required_glue_access(cls, attr_name, attr) is not None
        for attr_name, attr in inspect.getmembers_static(cls)
    )


def _get_required_glue_access(cls: type, attr_name: str, attr: Any) -> GlueAccess | None:
    access = getattr(attr, '__required_glue_access__', None)
    if access is not None:
        return access

    for base_cls in cls.__mro__:
        base_attr = base_cls.__dict__.get(attr_name)
        if base_attr is None:
            continue
        access = getattr(base_attr, '__required_glue_access__', None)
        if access is not None:
            return access

    return None
