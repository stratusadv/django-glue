from __future__ import annotations

import inspect
from abc import ABC, abstractmethod
from functools import cached_property
from typing import Any, TYPE_CHECKING

from django.http import HttpRequest

from django_glue.access import GlueAccess
from django_glue.glue.attributes import BaseGlueAttribute
from django_glue.exceptions import GlueMissingAttributeError
from django_glue.glue.context import GlueManifest

if TYPE_CHECKING:
    from django_glue.glue.metadata import GlueMetadata
    from django_glue.glue.policy import GluePolicy


class BaseGlue(ABC):
    """Native Glue runtime object that can serialize and handle attribute requests."""

    namespace: str

    def __init__(
        self,
        *,
        name: str,
        access: GlueAccess,
        request: HttpRequest,
    ) -> None:
        self.name = name
        self.access = access
        self.request = request
        self._policy: GluePolicy | None = None
        self._load_state = False

    @property
    def policy(self) -> GluePolicy:
        """Signed client-held policy for this request-bound Glue object."""
        from django_glue.glue.policy import GluePolicy  # noqa: PLC0415

        if self._policy is None:
            self._policy = GluePolicy.from_glue_object(glue_object=self)
        return self._policy

    @policy.setter
    def policy(self, value: GluePolicy) -> None:
        self._policy = value

    @property
    def manifest(self) -> GlueManifest:
        return GlueManifest(
            policy=self.policy,
            metadata=self.metadata,
        )

    @cached_property
    def attributes(self) -> dict[str, BaseGlueAttribute]:
        """Runtime attributes exposed by this object and its subjects."""
        attributes: dict[str, BaseGlueAttribute] = {}
        visited: set[int] = set()
        # Discover attributes on the GlueObject itself
        attributes.update(self._discover_attributes(target=self, visited=visited))
        # Discover attributes on each subject
        for subject in self.subjects.values():
            attributes.update(self._discover_attributes(target=subject, visited=visited))
        return attributes

    def _discover_attributes(
        self,
        target: Any,
        visited: set[int],
        path_prefix: str = '',
    ) -> dict[str, BaseGlueAttribute]:
        """
        Discover @Attribute-decorated members on a target object.

        Recursively walks nested value attributes that themselves contain
        @Attribute-decorated members.
        """
        from django_glue.glue.attributes.callable import CallableAttribute
        from django_glue.glue.attributes.value import ValueAttribute

        target_id = id(target)
        if target_id in visited:
            return {}
        visited.add(target_id)

        attributes: dict[str, BaseGlueAttribute] = {}
        cls = target.__class__

        for attr_name, attr in inspect.getmembers_static(cls):
            access = self._get_required_access(cls, attr_name, attr)
            if access is None:
                continue

            name = f'{path_prefix}.{attr_name}' if path_prefix else attr_name
            is_callable = getattr(attr, 'is_callable', True)
            if is_callable:
                attributes[name] = CallableAttribute(owner=self, name=name, access=access)
            else:
                attributes[name] = ValueAttribute(owner=self, name=name, access=access)

        # Second pass: recurse into nested value attributes
        for attr_name, class_attr in inspect.getmembers_static(cls):
            if attr_name.startswith('_') or not hasattr(class_attr, '__get__'):
                continue
            access = self._get_required_access(cls, attr_name, class_attr)
            if access is None or getattr(class_attr, 'is_callable', True):
                continue

            try:
                value = getattr(target, attr_name)
            except Exception:  # noqa: S112
                continue

            if value is None or callable(value):
                continue
            if not self._has_glue_attributes(value.__class__):
                continue

            nested_prefix = f'{path_prefix}.{attr_name}' if path_prefix else attr_name
            attributes.update(self._discover_attributes(
                target=value,
                visited=visited,
                path_prefix=nested_prefix,
            ))

        return attributes

    def _has_glue_attributes(self, cls: type) -> bool:
        """Check if a class has any @Attribute-decorated members."""
        return any(
            self._get_required_access(cls, attr_name, attr) is not None
            for attr_name, attr in inspect.getmembers_static(cls)
        )

    @staticmethod
    def _get_required_access(cls: type, attr_name: str, attr: Any) -> GlueAccess | None:
        """Get the required GlueAccess for an attribute, if it's a Glue attribute."""
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

    @property
    @abstractmethod
    def subjects(self) -> dict[str, Any]:
        """Objects whose @Attribute-decorated members are exposed through this GlueObject."""
        raise NotImplementedError

    @property
    @abstractmethod
    def identity(self) -> dict[str, Any]:
        """Object-specific target identity for the policy."""
        raise NotImplementedError

    @property
    @abstractmethod
    def state(self) -> Any:
        """Build mutable state for target."""
        raise NotImplementedError

    @cached_property
    @abstractmethod
    def metadata(self) -> GlueMetadata:
        """Build non-authoritative client metadata for target."""
        raise NotImplementedError

    # TODO: evaluate changing to from_glueattributerequest
    @classmethod
    @abstractmethod
    def from_policy(cls, policy: GluePolicy, request: HttpRequest) -> BaseGlue:
        """Reconstruct a GlueObject from a signed policy."""
        raise NotImplementedError

    def call_attribute(
        self,
        attribute_name: str,
        kwargs: dict[str, Any],
    ) -> Any:
        """Perform a callable attribute request against a resolved target."""
        glue_attribute = self.attributes.get(attribute_name, None)
        if not glue_attribute:
            raise GlueMissingAttributeError(attribute_name, self.name)

        self._load_state = True

        return glue_attribute.call(
            kwargs,
            context={
                'state': self.state,
                'attribute': attribute_name,
                'kwargs': kwargs,
                'policy': self.policy,
                'request': self.request,
            },
        )
