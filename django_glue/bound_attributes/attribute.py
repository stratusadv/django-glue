import inspect
from typing import Any
from pydantic import BaseModel
from django_glue.access.access import GlueAccess
from django_glue.utils import get_attr_from_path_string


class BoundProxyAttribute(BaseModel):
    name: str
    required_access: GlueAccess
    target_class_path: str
    is_callable: bool = True

    @property
    def target_class(self) -> type:
        target_class = get_attr_from_path_string(self.target_class_path)
        if not isinstance(target_class, type):
            msg = 'target_class_path for instance does not refer to a valid class.'
            raise ValueError(msg)
        return target_class

    @property
    def attribute(self) -> Any:
        target_class = self.target_class
        attr = getattr(target_class, self.name, None)
        if attr is None:
            msg = f'Could not find attribute named {self.name} on class {target_class.__name__}'
            raise ValueError(msg)
        return attr


def _discover_attributes_on_instance(
    root_target: Any,
    instance: Any,
    path_prefix: str,
    root_cls_name: str,
    visited: set[int] | None = None,
) -> dict[str, BoundProxyAttribute]:
    """Discover bound attributes on an instance from Attribute-decorated class attributes."""
    if visited is None:
        visited = set()
    instance_id = id(instance)
    if instance_id in visited:
        return {}
    visited.add(instance_id)

    bound_attributes: dict[str, BoundProxyAttribute] = {}
    cls = instance.__class__
    target_class_path = f'{root_target.__class__.__module__}.{root_target.__class__.__name__}'

    for attr_name, attr in inspect.getmembers_static(cls):
        required_access = _get_required_access(cls, attr_name, attr)
        if required_access is None:
            continue

        is_callable = getattr(attr, 'is_callable', True)
        full_name = f'{path_prefix}.{attr_name}' if path_prefix else attr_name
        bound_attributes[f'{root_cls_name}.{full_name}'] = BoundProxyAttribute(
            name=full_name,
            required_access=required_access,
            target_class_path=target_class_path,
            is_callable=is_callable,
        )

    bound_attributes.update(
        _discover_decorated_descriptor_attributes(
            root_target,
            instance,
            path_prefix,
            root_cls_name,
            visited,
        )
    )

    return bound_attributes


def _has_decorated_attributes(cls: type) -> bool:
    for attr_name, attr in inspect.getmembers_static(cls):
        if _get_required_access(cls, attr_name, attr) is not None:
            return True
    return False


def _get_required_access(cls: type, attr_name: str, attr: Any) -> GlueAccess | None:
    required_access = getattr(attr, '__required_glue_access__', None)
    if required_access is not None:
        return required_access

    for base_cls in cls.__mro__:
        base_attr = base_cls.__dict__.get(attr_name)
        if base_attr is None:
            continue
        required_access = getattr(base_attr, '__required_glue_access__', None)
        if required_access is not None:
            return required_access

    return None


def _discover_decorated_descriptor_attributes(
    root_target: Any,
    instance: Any,
    path_prefix: str,
    root_cls_name: str,
    visited: set[int],
) -> dict[str, BoundProxyAttribute]:
    bound_attributes: dict[str, BoundProxyAttribute] = {}

    for attr_name, class_attr in inspect.getmembers_static(instance.__class__):
        if attr_name.startswith('_'):
            continue
        if not hasattr(class_attr, '__get__'):
            continue

        try:
            attr = getattr(instance, attr_name)
        except Exception:
            continue

        if attr is None or callable(attr):
            continue
        if not _has_decorated_attributes(attr.__class__):
            continue

        nested_prefix = f'{path_prefix}.{attr_name}' if path_prefix else attr_name
        bound_attributes.update(
            _discover_attributes_on_instance(root_target, attr, nested_prefix, root_cls_name, visited)
        )

    return bound_attributes


def discover_bound_attributes_on_target(target: Any) -> dict[str, BoundProxyAttribute]:
    """Discover all bound attributes for a single target."""
    return _discover_attributes_on_instance(target, target, '', target.__class__.__name__)


# Resolve forward references in ProxyPolicy now that BoundProxyAttribute is defined
from django_glue.proxies.policy import ProxyPolicy
ProxyPolicy.model_rebuild()
