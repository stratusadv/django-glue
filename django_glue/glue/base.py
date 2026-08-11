from __future__ import annotations

import json
from abc import ABC, abstractmethod
from functools import cached_property
from typing import Any, TYPE_CHECKING

from django_glue.encoders import GlueResponseJSONEncoder
from django_glue.exceptions import (
    GlueAccessError,
    GlueCalledStateAttributeError,
    GlueMissingAttributeError,
)
from django_glue.glue.attributes.callable import CallableAttribute
from django_glue.glue.attributes.collector import GlueAttributeCollector
from django_glue.glue.attributes.glue_object import GlueObjectAttribute
from django_glue.glue.attributes.state import StateAttribute
from django_glue.glue.context import GlueManifest
from django_glue.response import GlueResponse

if TYPE_CHECKING:
    from django_glue.resolver.attribute_call.context import AttributeCallRequestContext
    from django_glue.glue.attributes import BaseGlueAttribute
    from django_glue.access import GlueAccess
    from django.http import HttpRequest, JsonResponse
    from django_glue.glue.policy import GluePolicy


class BaseGlue(ABC):
    """Native Glue runtime object that can serialize and handle attribute requests."""

    namespace: str

    def __init__(
        self,
        *,
        name: str | None = None,
        access: GlueAccess,
    ) -> None:
        self.name = name or self.namespace
        self.access = access
        self.request: HttpRequest | None = None

    @property
    def is_bound(self) -> bool:
        """True if this glue object is bound to a request context."""
        return self.request is not None

    @cached_property
    def policy(self) -> GluePolicy:
        """Signed client-held policy for this request-bound Glue object."""
        from django_glue.glue.policy import GluePolicy  # noqa: PLC0415

        if not self.is_bound:
            msg = (
                f"Cannot generate policy for unbound GlueObject '{self.name}'. "
                'Bind to a request first.'
            )
            raise RuntimeError(msg)

        return GluePolicy.from_glue_object(glue_object=self)

    @property
    def manifest(self) -> GlueManifest:
        return GlueManifest(
            policy=self.policy,
            metadata=self.metadata,
        )

    @cached_property
    def _attribute_collector(self) -> GlueAttributeCollector:
        """The attribute collector for this glue object."""
        collector = GlueAttributeCollector(self)
        collector.collect()
        return collector

    @property
    def attributes(self) -> dict[str, BaseGlueAttribute]:
        """Runtime attributes exposed by this object and its providers."""
        return self._attribute_collector.glue_attributes

    @property
    def attribute_providers(self) -> dict[str, Any]:
        """Objects whose @Attribute-decorated members are exposed through this GlueObject."""
        return {}

    @property
    def identity(self) -> dict[str, Any]:
        """
        Object-specific target identity for the policy.

        By default, auto-generates identity from attributes marked with
        identity=True (e.g., @Glue.property(identity=True) or
        @Glue.attribute(access=..., identity=True)).

        Override in subclasses for custom behavior.
        """
        return self._build_identity_from_attributes()

    def _build_identity_from_attributes(self) -> dict[str, Any]:
        """Build identity dict from collected identity attributes."""
        from django_glue.glue.policy import GluePolicy

        identity_data: dict[str, Any] = {}

        for attr in self._attribute_collector.identity_attributes:
            value = attr.get()

            if isinstance(attr, GlueObjectAttribute):
                # For nested Glue objects, store the full policy
                glue_object: BaseGlue = value
                glue_object.request = self.request
                policy = GluePolicy.from_glue_object(glue_object=glue_object)
                identity_data[attr.name] = policy.model_dump()
            else:
                # Serialize using GlueResponseJSONEncoder for dates, etc.
                identity_data[attr.name] = json.loads(
                    json.dumps(value, cls=GlueResponseJSONEncoder)
                )

        return identity_data

    @cached_property
    def state(self) -> dict[str, Any]:
        """Build mutable state from attributes."""
        return {
            name: attribute.state
            for name, attribute in self.attributes.items()
            if isinstance(attribute, StateAttribute | GlueObjectAttribute)
        }

    @cached_property
    def metadata(self) -> dict[str, Any]:
        """Build non-authoritative client metadata for target."""
        return {
            'attributes': {
                name: attr.metadata
                for name, attr in self.attributes.items()
            },
        }

    @classmethod
    def from_attribute_call_resolver_context(
        cls,
        context: AttributeCallRequestContext
    ) -> BaseGlue:
        glue_object = cls._reconstruct_from_policy(context.target_glue_policy)
        glue_object.request = context.request

        attribute = glue_object.attributes.get(context.target_attribute_name)
        loads_state = getattr(attribute, 'loads_state', True) if attribute else True
        if attribute and loads_state:
            state = context.target_glue_client_state or {}
            if isinstance(loads_state, list | tuple):
                state = {
                    key: state[key]
                    for key in loads_state
                    if key in state
                }
            glue_object._load_client_state(state)
            glue_object._invalidate_attributes()

        return glue_object

    @classmethod
    @abstractmethod
    def _reconstruct_from_policy(cls, policy: GluePolicy) -> BaseGlue:
        """Reconstruct a GlueObject from a signed policy."""
        raise NotImplementedError

    def _load_client_state(self, state: dict[str, Any]) -> None:
        """Apply client-provided state attributes to this Glue object."""
        for name, attribute in self.attributes.items():
            if not isinstance(attribute, StateAttribute):
                continue
            if name not in state:
                continue

            attribute_state = state[name]
            value = (
                attribute_state.get('value')
                if isinstance(attribute_state, dict)
                else attribute_state
            )
            setattr(self, name, value)

    def _invalidate_attributes(self) -> None:
        """Discard discovered attributes after target state hydration."""
        self.__dict__.pop('attributes', None)
        self.__dict__.pop('_attribute_collector', None)
        self.__dict__.pop('policy', None)
        self.__dict__.pop('metadata', None)
        self._invalidate_state()

    def _invalidate_state(self) -> None:
        self.__dict__.pop('state', None)

    def process_attribute_call(
        self,
        call_context: AttributeCallRequestContext
    ) -> JsonResponse:
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

        call_result = glue_attribute.call(call_context)
        self._invalidate_attributes()

        response_extra = {}
        if getattr(glue_attribute, 'updates_state', True):
            response_extra = {
                'state': self.state,
                'policy': self.policy,
                'metadata': self.metadata,
            }

        return GlueResponse.from_result(call_result).to_json_response(
            glue_object=self,
            **response_extra,
        )
