from __future__ import annotations

import inspect
from typing import Any, get_type_hints

# Runtime import required: build_attribute_kwargs injects this into get_type_hints()
# so Glue.Attribute methods may annotate request parameters as HttpRequest.
from django.http import HttpRequest

from django_glue.access import GlueAccess
from django_glue.glue.attributes.base import BaseGlueAttribute


def discover_glue_attributes(owner: Any) -> dict[str, BaseGlueAttribute]:
    return _discover_glue_attributes(owner=owner, instance=owner, path_prefix='', visited=set())


def _discover_glue_attributes(
    *,
    owner: Any,
    instance: Any,
    path_prefix: str,
    visited: set[int],
) -> dict[str, BaseGlueAttribute]:
    from django_glue.glue.attributes.declared import DeclaredGlueAttribute

    instance_id = id(instance)
    if instance_id in visited:
        return {}
    visited.add(instance_id)

    attributes: dict[str, BaseGlueAttribute] = {}
    cls = instance.__class__

    for attr_name, attr in inspect.getmembers_static(cls):
        access = _get_required_glue_access(cls, attr_name, attr)
        if access is None:
            continue

        name = f'{path_prefix}.{attr_name}' if path_prefix else attr_name
        attributes[name] = DeclaredGlueAttribute(
            name=name,
            owner=owner,
            access=access,
            is_callable=getattr(attr, 'is_callable', True),
        )

    for attr_name, class_attr in inspect.getmembers_static(cls):
        if attr_name.startswith('_') or not hasattr(class_attr, '__get__'):
            continue
        access = _get_required_glue_access(cls, attr_name, class_attr)
        if access is None or getattr(class_attr, 'is_callable', True):
            continue

        try:
            value = getattr(instance, attr_name)
        except Exception:
            continue

        if value is None or callable(value):
            continue
        if not _class_has_glue_attributes(value.__class__):
            continue

        nested_prefix = f'{path_prefix}.{attr_name}' if path_prefix else attr_name
        attributes.update(
            _discover_glue_attributes(
                owner=owner,
                instance=value,
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


def build_attribute_kwargs(
    attribute: Any,
    *,
    request_kwargs: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    unwrapped = inspect.unwrap(attribute)
    signature = inspect.signature(unwrapped)
    function_globals = getattr(unwrapped, '__globals__', {})
    type_hints = get_type_hints(unwrapped, globalns={**function_globals, 'HttpRequest': HttpRequest})
    accepts_var_kwargs = any(
        param.kind == inspect.Parameter.VAR_KEYWORD
        for param in signature.parameters.values()
    )

    for param_name, param in signature.parameters.items():
        if param_name == 'self':
            continue
        if param_name in context:
            kwargs[param_name] = context[param_name]
            continue
        hint = type_hints.get(param_name)
        if hint is not None and isinstance(hint, type) and issubclass(hint, HttpRequest):
            kwargs[param_name] = context['request']
            continue
        if param_name in request_kwargs:
            kwargs[param_name] = request_kwargs[param_name]
            continue
        if param_name not in kwargs and param.default is inspect.Parameter.empty:
            continue

    if accepts_var_kwargs:
        for key, value in request_kwargs.items():
            kwargs.setdefault(key, value)

    return kwargs
