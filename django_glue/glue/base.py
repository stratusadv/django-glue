from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, TYPE_CHECKING

from django.http import HttpRequest

from django_glue.access import GlueAccess
from django_glue.glue.attributes import BaseGlueAttribute, discover_glue_attributes
from django_glue.exceptions import GlueMissingAttributeError
from django_glue.glue.manifest import GlueManifest

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
            state=self.state, # TODO: Defer loading state
            metadata=self.metadata,
        )

    @property
    def attributes(self) -> dict[str, BaseGlueAttribute]:
        """Runtime attributes exposed by this object."""
        return discover_glue_attributes(self)

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

    @property
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

    # TODO: why do we need policy and request again?
    def call_attribute(
        self,
        state: Any,
        attribute_name: str,
        kwargs: dict[str, Any],
        policy: GluePolicy,
        request: HttpRequest,
    ) -> Any:
        """Perform a callable attribute request against a resolved target."""
        if not attribute_name:
            raise GlueMissingAttributeError('', policy.name)

        attribute = self.attributes.get(attribute_name)
        if attribute is None:
            raise GlueMissingAttributeError(attribute_name, policy.name)

        return attribute.call(
            kwargs,
            context={
                'state': state,
                'attribute': attribute_name,
                'kwargs': kwargs,
                'policy': policy,
                'request': request,
            },
        )
