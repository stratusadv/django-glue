from __future__ import annotations

from abc import ABC, abstractmethod
from functools import cached_property
from typing import Any, TYPE_CHECKING

from django_glue.exceptions import GlueAccessError, GlueCalledStateAttributeError, GlueMissingAttributeError
from django_glue.glue.attributes.callable import CallableAttribute
from django_glue.glue.attributes.collector import GlueAttributeCollector
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

    @property
    def is_bound(self) -> bool:
        """True if this glue object is bound to a request context."""
        return self.request is not None

    @cached_property
    def policy(self) -> GluePolicy:
        """Signed client-held policy for this request-bound Glue object."""
        from django_glue.glue.policy import GluePolicy  # noqa: PLC0415

        if not self.is_bound:
            msg = f"Cannot generate policy for unbound GlueObject '{self.name}'. Bind to a request first."
            raise RuntimeError(msg)

        return GluePolicy.from_glue_object(glue_object=self)

    @property
    def manifest(self) -> GlueManifest:
        return GlueManifest(
            policy=self.policy,
            metadata=self.metadata,
        )

    @cached_property
    def attributes(self) -> dict[str, BaseGlueAttribute]:
        """Runtime attributes exposed by this object and its providers."""
        return GlueAttributeCollector(self).collect()

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
            name: getattr(attribute, 'state', None)
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
        glue_object = cls._reconstruct_from_policy(context.target_glue_policy)
        glue_object.request = context.request

        attribute = glue_object.attributes.get(context.target_attribute_name)
        if attribute and getattr(attribute, 'loads_state', True):
            glue_object._load_client_state(context.target_glue_client_state or {})
            glue_object._invalidate_attributes()

        return glue_object

    @classmethod
    @abstractmethod
    def _reconstruct_from_policy(cls, policy: GluePolicy) -> BaseGlue:
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

        call_result = glue_attribute.call(call_context)

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
