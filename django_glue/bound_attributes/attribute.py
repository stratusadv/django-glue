import inspect
from typing import Any, Union
from pydantic import BaseModel
from django_glue.access.access import GlueAccess
from django_glue.utils import get_attr_from_path_string, get_attr_from_path_string_on_instance


class AttributeConfig(BaseModel):
    """Configuration for a bound attribute in GlueMeta."""
    access: GlueAccess


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


def _parse_attribute_config(access_or_config: Union[GlueAccess, dict]) -> AttributeConfig:
    """Back compat: accept GlueAccess, dict, or AttributeConfig."""
    if isinstance(access_or_config, AttributeConfig):
        return access_or_config
    if isinstance(access_or_config, GlueAccess):
        return AttributeConfig(access=access_or_config)
    if isinstance(access_or_config, dict):
        return AttributeConfig(**access_or_config)
    return AttributeConfig(access=access_or_config)


def _discover_attributes_on_instance(
    root_target: Any,
    instance: Any,
    path_prefix: str,
    root_cls_name: str,
) -> dict[str, BoundProxyAttribute]:
    """Discover bound attributes on an instance: @attribute-decorated methods + GlueMeta."""
    bound_attributes: dict[str, BoundProxyAttribute] = {}
    cls = instance.__class__
    target_class_path = f'{root_target.__class__.__module__}.{root_target.__class__.__name__}'

    # Scan for @attribute-decorated methods
    for attr_name, attr in inspect.getmembers(cls):
        required_access = getattr(attr, '__required_glue_access__', None)
        if required_access is None:
            for base_cls in cls.__mro__:
                base_attr = base_cls.__dict__.get(attr_name)
                if base_attr is not None:
                    required_access = getattr(base_attr, '__required_glue_access__', None)
                    if required_access is not None:
                        break

        if required_access is None:
            continue

        full_name = f'{path_prefix}.{attr_name}' if path_prefix else attr_name
        bound_attributes[f'{root_cls_name}.{full_name}'] = BoundProxyAttribute(
            name=full_name,
            required_access=required_access,
            target_class_path=target_class_path,
            is_callable=True,
        )

    # Scan for GlueMeta
    glue_meta = getattr(instance, 'GlueMeta', None)
    if not glue_meta:
        return bound_attributes

    # GlueMeta.attributes — callable methods + nested subobjects with GlueMeta
    for attr_name, config in getattr(glue_meta, 'attributes', None) or []:
        cfg = _parse_attribute_config(config)
        attr = get_attr_from_path_string_on_instance(instance, attr_name)
        if attr is None:
            continue

        if callable(attr):
            full_name = f'{path_prefix}.{attr_name}' if path_prefix else attr_name
            bound_attributes[f'{root_cls_name}.{full_name}'] = BoundProxyAttribute(
                name=full_name,
                required_access=cfg.access,
                target_class_path=target_class_path,
                is_callable=True,
            )
        elif hasattr(attr, 'GlueMeta'):
            # Non-callable with GlueMeta — recurse into it
            nested_prefix = f'{path_prefix}.{attr_name}' if path_prefix else attr_name
            bound_attributes.update(
                _discover_attributes_on_instance(root_target, attr, nested_prefix, root_cls_name)
            )

    # GlueMeta.exposed_attributes — non-callable (properties, plain data)
    for attr_name, config in getattr(glue_meta, 'exposed_attributes', None) or []:
        cfg = _parse_attribute_config(config)
        full_name = f'{path_prefix}.{attr_name}' if path_prefix else attr_name
        bound_attributes[f'{root_cls_name}.{full_name}'] = BoundProxyAttribute(
            name=full_name,
            required_access=cfg.access,
            target_class_path=target_class_path,
            is_callable=False,
        )

    return bound_attributes


def discover_bound_attributes_on_target(target: Any) -> dict[str, BoundProxyAttribute]:
    """Discover all bound attributes for a single target: @attribute-decorated methods + GlueMeta."""
    return _discover_attributes_on_instance(target, target, '', target.__class__.__name__)


# Resolve forward references in ProxyPolicy now that BoundProxyAttribute is defined
from django_glue.proxies.policy import ProxyPolicy
ProxyPolicy.model_rebuild()
