from __future__ import annotations

import inspect
from abc import ABC, abstractmethod
from functools import cached_property
from typing import Any, TYPE_CHECKING


from django_glue.exceptions import GlueAccessError, GlueCalledStateAttributeError, GlueMissingAttributeError, GlueRequestError
from django_glue.glue.attributes.callable import CallableAttribute
from django_glue.glue.attributes.container import ContainerAttribute
from django_glue.glue.attributes.readable import ReadableAttribute
from django_glue.glue.attributes.state import StateAttribute
from django_glue.glue.context import GlueManifest
from django_glue.response import GlueResponse

if TYPE_CHECKING:
    from django_glue.glue.schemas import AttributeCallResolverContext
    from django_glue.glue.attributes import BaseGlueAttribute
    from django_glue.access import GlueAccess
    from django.http import HttpRequest
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
    ) -> None:
        self.name = name
        self.access = access
        self.request: HttpRequest | None = None
        self._policy: GluePolicy | None = None

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
        for subject in self.attribute_providers.values():
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

        target_id = id(target)
        if target_id in visited:
            return {}
        visited.add(target_id)

        attributes: dict[str, BaseGlueAttribute] = {}
        cls = target.__class__
        resolved_values: dict[str, Any] = {}

        for attr_name, attr in inspect.getmembers_static(cls):
            access = self._get_required_access(cls, attr_name, attr)
            if access is None:
                continue

            name = f'{path_prefix}.{attr_name}' if path_prefix else attr_name
            # If discovering on a provider (not self), pass target for resolution
            resolve_target = target if target is not self else None
            is_callable = getattr(attr, 'is_callable', True)
            if is_callable:
                loads_state = getattr(attr, 'loads_state', True)
                attributes[name] = CallableAttribute(
                    owner=self,
                    name=attr_name,
                    access=access,
                    loads_state=loads_state,
                    target=resolve_target,
                )
            else:
                try:
                    value = getattr(target, attr_name)
                except Exception:  # noqa: S112
                    value = None

                resolved_values[attr_name] = value

                if isinstance(getattr(attr, 'target', None), property):
                    attributes[name] = ReadableAttribute(
                        owner=self,
                        name=attr_name,
                        access=access,
                        target=resolve_target,
                    )
                elif value is not None and self._has_glue_attributes(value.__class__):
                    attributes[name] = ContainerAttribute(
                        owner=self,
                        name=attr_name,
                        access=access,
                        target=resolve_target,
                    )
                else:
                    attributes[name] = StateAttribute(
                        owner=self,
                        name=attr_name,
                        access=access,
                        target=resolve_target,
                    )

        # Second pass: recurse into nested value attributes
        for attr_name, class_attr in inspect.getmembers_static(cls):
            if attr_name.startswith('_') or not hasattr(class_attr, '__get__'):
                continue
            access = self._get_required_access(cls, attr_name, class_attr)
            if access is None or getattr(class_attr, 'is_callable', True):
                continue

            if attr_name not in resolved_values:
                continue

            value = resolved_values[attr_name]
            if value is None or callable(value):
                continue
            if not self._has_glue_attributes(value.__class__):
                continue

            nested_prefix = f'{path_prefix}.{attr_name}' if path_prefix else attr_name
            nested_attrs = self._discover_attributes(
                target=value,
                visited=visited,
                path_prefix=nested_prefix,
            )
            attributes.update(nested_attrs)

        return attributes

    def _has_glue_attributes(self, cls: type) -> bool:
        """Check if a class has any @Attribute-decorated members."""
        return any(
            self._get_required_access(cls, attr_name, attr) is not None
            for attr_name, attr in inspect.getmembers_static(cls)
        )

    # TODO: this method smells
    @staticmethod
    def _get_required_access(target_class: type, attr_name: str, attr: Any) -> GlueAccess | None:
        """Get the required GlueAccess for an attribute, if it's a Glue attribute."""
        access = getattr(attr, '__required_glue_access__', None)
        if access is not None:
            return access

        for base_cls in target_class.__mro__:
            base_attr = base_cls.__dict__.get(attr_name)
            if base_attr is None:
                continue
            access = getattr(base_attr, '__required_glue_access__', None)
            if access is not None:
                return access

        return None

    @property
    def attribute_providers(self) -> dict[str, Any]:
        """Objects whose @Attribute-decorated members are exposed through this GlueObject."""
        return {}

    @property
    @abstractmethod
    def identity(self) -> dict[str, Any]:
        """Object-specific target identity for the policy."""
        raise NotImplementedError

    @property
    def state(self) -> dict[str, Any]:
        """Build mutable state from attributes."""
        return {
            name: attribute.state
            for name, attribute in self.attributes.items()
            if hasattr(attribute, 'state')
        }

    @cached_property
    @abstractmethod
    def metadata(self) -> GlueMetadata:
        """Build non-authoritative client metadata for target."""
        raise NotImplementedError

    @classmethod
    def from_attribute_call_resolver_context(
        cls,
        context: AttributeCallResolverContext
    ) -> BaseGlue:
        glue_object = cls._from_policy(context.target_glue_policy)
        glue_object.request = context.request

        attribute = glue_object.attributes.get(context.target_attribute_name)
        if attribute and getattr(attribute, 'loads_state', True):
            glue_object._load_client_state(context.target_glue_client_state or {})
            glue_object._invalidate_attributes()

        return glue_object

    @classmethod
    @abstractmethod
    def _from_policy(cls, policy: GluePolicy) -> BaseGlue:
        """Reconstruct a GlueObject from a signed policy."""
        raise NotImplementedError

    def _load_client_state(self, state: dict[str, Any]) -> None:  # noqa: B027
        """Apply client-provided state to subjects. Override in subclasses."""

    def _invalidate_attributes(self) -> None:
        """Discard discovered attributes after target state hydration."""
        self.__dict__.pop('attributes', None)

    def process_attribute_call(
        self,
        call_context: AttributeCallResolverContext
    ) -> dict[str, Any]:
        """Perform a callable attribute request against a resolved target."""
        glue_attribute = self.attributes.get(call_context.target_attribute_name, None)
        if not glue_attribute:
            raise GlueMissingAttributeError(call_context.target_attribute_name, self.name)

        if not isinstance(glue_attribute, CallableAttribute):
            raise GlueCalledStateAttributeError(call_context.target_attribute_name, self.name)

        if not call_context.target_glue_policy.access.has_access(glue_attribute.required_access):
            raise GlueAccessError(
                attribute=call_context.target_attribute_name,
                required_access=glue_attribute.required_access.value,
                current_access=call_context.target_glue_policy.access.value,
            )

        if call_context.target_attribute_name not in call_context.target_glue_policy.attributes:
            raise GlueMissingAttributeError(
                call_context.target_attribute_name,
                call_context.target_glue_policy.name
            )

        if not isinstance(glue_attribute, CallableAttribute):
            raise GlueRequestError(
                code='attribute_not_callable',
                message=f"Attribute '{call_context.target_attribute_name}' is not callable.",
                details={'attribute': call_context.target_attribute_name},
                status=422,
            )

        call_result = glue_attribute.call(call_context)
        self._policy = None

        call_response_data = {
            'data': {
                'state': self.state,
                'policy': self.policy,
                'metadata': self.metadata,
            },
            'status': 200
        }

        if isinstance(call_result, GlueResponse):
            call_response_data['data']['result'] = call_result.result
            call_response_data['data']['messages'] = [
                message.to_dict() for message in call_result.messages
            ]
            call_response_data['status'] = call_result.status
        else:
            call_response_data['data']['result'] = call_result
            call_response_data['data']['messages'] = []

        # TODO: Statically typed dict here -> bad
        return call_response_data
