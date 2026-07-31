from __future__ import annotations

import inspect
from typing import Any, TYPE_CHECKING

from django_glue.glue.attributes.callable import CallableAttribute
from django_glue.glue.attributes.composite import CompositeStateAttribute
from django_glue.glue.attributes.declared import DeclaredAttributeOptions
from django_glue.glue.attributes.readonly import ReadOnlyAttribute

if TYPE_CHECKING:
    from django_glue.glue.attributes.base import BaseGlueAttribute
    from django_glue.glue.base import BaseGlue


class GlueAttributeCollector:
    """
    Discovers @Attribute-decorated members on a glue object and its providers.

    Recursively walks nested value attributes that themselves contain
    @Attribute-decorated members.
    """

    def __init__(self, root_glue_owner: BaseGlue) -> None:
        self.root_glue_owner = root_glue_owner
        self.visited_attribute_owners: set[int] = set()
        self.glue_attributes: dict[str, BaseGlueAttribute] = {}

    def collect(self) -> dict[str, BaseGlueAttribute]:
        """Collect all attributes from the owner and its providers."""
        self._collect_glue_attributes_from_root()
        self._collect_glue_attributes_from_glue_attr_providers()
        return self.glue_attributes

    def _collect_glue_attributes_from_root(self) -> None:
        """Discover attributes defined directly on the owner."""
        self._collect_attrs_from_glue_attr_owner(
            glue_attr_owner=self.root_glue_owner,
            discovery_path_prefix=''
        )

    def _collect_glue_attributes_from_glue_attr_providers(self) -> None:
        """Discover attributes from the owner's attribute providers."""
        for glue_attribute_provider in self.root_glue_owner.attribute_providers.values():
            self._collect_attrs_from_glue_attr_owner(
                glue_attr_owner=glue_attribute_provider,
                discovery_path_prefix=''
            )

    def _collect_attrs_from_glue_attr_owner(
            self,
            glue_attr_owner: Any,
            discovery_path_prefix: str
        ) -> None:
        """Discover attributes on a glue attribute owner, tracking visited objects to prevent cycles."""
        if self._glue_attr_owner_is_visited(glue_attr_owner):
            return

        self._mark_glue_attr_owner_visited(glue_attr_owner)

        owner_class = glue_attr_owner.__class__
        attr_owner_instance = glue_attr_owner if glue_attr_owner is not self.root_glue_owner else None

        for attr_name, attr in inspect.getmembers_static(owner_class):
            options = self._get_glue_options(owner_class, attr_name, attr)
            if options is None:
                continue

            glue_attr_qualified_name = self._build_qualified_name(
                path_prefix=discovery_path_prefix,
                attr_name=attr_name
            )

            self._create_glue_attribute(
                glue_attr_owner=glue_attr_owner,
                attr_owner_instance=attr_owner_instance,
                qualified_name=glue_attr_qualified_name,
                attr_name=attr_name,
                options=options,
            )

    def _create_glue_attribute(
        self,
        glue_attr_owner: Any,
        attr_owner_instance: Any | None,
        qualified_name: str,
        attr_name: str,
        options: DeclaredAttributeOptions,
    ) -> None:
        """
        Create and register a glue attribute, recursing depth-first into objects
        that are detected to have nested glue attributes.
        """
        if options.is_callable:
            self.glue_attributes[qualified_name] = self._create_callable_attribute(
                attr_name, options, attr_owner_instance
            )
            return

        value = getattr(glue_attr_owner, attr_name)
        self.glue_attributes[qualified_name] = self._create_state_attribute(
            attr_name, options, attr_owner_instance, value
        )

        # Depth-first: recurse immediately into containers
        if value is not None and self._has_glue_attributes(value.__class__):
            self._collect_attrs_from_glue_attr_owner(
                glue_attr_owner=value,
                discovery_path_prefix=qualified_name
            )

    def _glue_attr_owner_is_visited(self, glue_attr_owner: Any) -> bool:
        """Check if a glue attribute owner has already been visited."""
        return id(glue_attr_owner) in self.visited_attribute_owners

    def _mark_glue_attr_owner_visited(self, glue_attr_owner: Any) -> None:
        """Mark a glue attribute owner as visited to prevent cycles."""
        self.visited_attribute_owners.add(id(glue_attr_owner))

    def _create_callable_attribute(
        self,
        attr_name: str,
        options: DeclaredAttributeOptions,
        attr_owner_instance: Any | None,
    ) -> CallableAttribute:
        """Create a CallableAttribute from a decorated method."""
        return CallableAttribute(
            owner=self.root_glue_owner,
            name=attr_name,
            access=options.access,
            loads_state=options.loads_state,
            attr_owner_instance=attr_owner_instance,
        )

    def _create_state_attribute(
        self,
        attr_name: str,
        options: DeclaredAttributeOptions,
        attr_owner_instance: Any | None,
        value: Any,
    ) -> BaseGlueAttribute:
        # These are the only potential state attribute types right now.
        # More likely to be added in the future.
        if value is not None and self._has_glue_attributes(value.__class__):
            return CompositeStateAttribute(
                owner=self.root_glue_owner,
                name=attr_name,
                access=options.access,
                attr_owner_instance=attr_owner_instance,
            )

        # Fallback for primitive values declared as attributes
        return ReadOnlyAttribute(
            owner=self.root_glue_owner,
            name=attr_name,
            access=options.access,
            attr_owner_instance=attr_owner_instance,
        )

    def _has_glue_attributes(self, cls: type) -> bool:
        """Check if a class has any @DeclaredAttribute-decorated members."""
        return any(
            self._get_glue_options(cls, attr_name, attr) is not None
            for attr_name, attr in inspect.getmembers_static(cls)
        )

    @staticmethod
    def _get_glue_options(
        target_class: type,
        attr_name: str,
        attr: Any
    ) -> DeclaredAttributeOptions | None:
        """Get the glue options for an attribute, if it's a glue attribute."""
        options = getattr(attr, '__glue_options__', None)
        if options is not None:
            return options

        for base_cls in target_class.__mro__:
            base_attr = base_cls.__dict__.get(attr_name)
            if base_attr is None:
                continue
            options = getattr(base_attr, '__glue_options__', None)
            if options is not None:
                return options

        return None

    @staticmethod
    def _build_qualified_name(path_prefix: str, attr_name: str) -> str:
        """Build a dot-separated qualified attribute name."""
        return f'{path_prefix}.{attr_name}' if path_prefix else attr_name
