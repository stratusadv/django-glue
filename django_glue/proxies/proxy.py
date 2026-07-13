"""
Base proxy class for Django Glue.

This module provides the abstract base class that all proxy types inherit from,
defining the core interface for policy registration, access control, and
bound attribute discovery.
"""

from __future__ import annotations

from abc import ABC
import inspect
from typing import Any, TYPE_CHECKING, Self

from django_glue.constants import DJANGO_GLUE_PROXIES_REQUEST_ATTR_KEY

if TYPE_CHECKING:
    from django.http import HttpRequest
    from django_glue.proxies.state import BaseProxyState
    from django_glue.access.access import GlueAccess
    from django_glue.bound_attributes.attribute import BoundProxyAttribute
    from django_glue.resolver.attribute_event.schemas import BoundProxyAttributeEvent


class BaseGlueProxy(ABC):
    """
    Abstract base class for all Django Glue proxies.

    A proxy is a thin composition of identity (name, namespace, access),
    state (Django objects), and bound attributes (callable operations).

    Subclasses must define:
        _subject_type: The type of object this proxy wraps (e.g., Model, QuerySet).
        _state_class: The state class that holds Django objects for this proxy type.

    Attributes:
        name: Identifier used to reference this proxy from JavaScript.
        namespace: Namespace under which this proxy is accessible (model, querySet, form, etc.).
        access: The access level granted to the client (VIEW, CHANGE, or DELETE).
        state: The proxy's state object holding Django instances.

    """

    _subject_type: type
    _state_class: type[BaseProxyState]

    def __init__(
        self,
        name: str,
        namespace: str,
        access: GlueAccess,
        state: BaseProxyState,
    ) -> None:
        self.name = name
        self.namespace = namespace
        self.access = access
        self.state = state
        self.session_id: str | None = None

    @classmethod
    def _from_attribute_event(cls, event: BoundProxyAttributeEvent) -> Self:
        state = cls._state_class.deserialize(event)
        proxy = cls(event.policy.name, event.policy.namespace, event.policy.access, state)
        proxy.session_id = event.policy.session_id
        return proxy

    @classmethod
    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        is_abstract = inspect.isabstract(cls)
        if not hasattr(cls, '_subject_type') and not is_abstract:
            msg = (
                f"BaseGlueProxy subclass {cls.__name__} must define '_subject_type "
                "attribute that matches the expected type of the __init__ 'target' parameter."
            )
            raise TypeError(msg)
        if not hasattr(cls, '_state_class') and not is_abstract:
            msg = (
                f"BaseGlueProxy subclass {cls.__name__} must define '_state_class "
                "attribute that provides state management for this proxy type."
            )
            raise TypeError(msg)

    # --- Policy Registration ---

    def _register_with_request(self, request: HttpRequest) -> None:
        from django_glue.proxies.policy import ProxyPolicy  # noqa: PLC0415

        if DJANGO_GLUE_PROXIES_REQUEST_ATTR_KEY not in request.__dict__:
            request.__dict__[DJANGO_GLUE_PROXIES_REQUEST_ATTR_KEY] = {}

        if request.session.session_key is None:
            request.session.save()
        self.session_id = request.session.session_key

        request.__dict__[DJANGO_GLUE_PROXIES_REQUEST_ATTR_KEY][self.name] = {
            'state': self.state.serialize() if self.state else {},
            'policy': ProxyPolicy.new_signed_policy({
                'session_id': self.session_id,
                'name': self.name,
                'access': self.access,
                'bound_attributes': self._policy_data,
                'subject_details': {
                    'namespace': self.namespace,
                    **self._custom_policy_details,
                },
            }).model_dump(),
        }

    # --- Discovery for attributes that are bound directly on the target classes ---
    @property
    def targets(self) -> list[Any]:
        return [self]

    def _get_bound_attribute_owner(self, bound_attribute: BoundProxyAttribute) -> Any:
        for target in self.targets:
            if isinstance(target, bound_attribute.target_class):
                return target
        return None

    @property
    def _custom_policy_details(self) -> dict:
        return {}

    @property
    def _policy_data(self) -> dict:
        bound_attributes = self.discover_bound_attributes()
        return {
            bound_attribute_name: bound_attribute.model_dump(exclude_none=True)
            for bound_attribute_name, bound_attribute in bound_attributes.items()
            if self._get_bound_attribute_owner(bound_attribute) is not None
        }

    def discover_bound_attributes(self) -> dict[str, BoundProxyAttribute]:
        from django_glue.bound_attributes.attribute import discover_bound_attributes_on_target  # noqa: PLC0415

        all_bound_attributes: dict[str, BoundProxyAttribute] = {}
        for target in self.targets:
            all_bound_attributes.update(discover_bound_attributes_on_target(target))
        return all_bound_attributes
