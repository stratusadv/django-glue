from __future__ import annotations

import inspect
import json
from abc import ABC, abstractmethod
from dataclasses import replace
from functools import cached_property
from typing import TYPE_CHECKING, Any, Callable, Self

from django.http import HttpRequest

from django_glue.access import GlueAccess
from django_glue.encoders import GlueResponseJSONEncoder
from django_glue.exceptions import (
    GlueAccessError,
    GlueAuthorizationError,
    GlueCalledStateAttributeError,
    GlueMissingAttributeError,
    GlueRequestError,
    GlueRequestErrorCode,
)
from django_glue.glue import address
from django_glue.glue.attributes.collector import GlueAttributeCollector
from django_glue.glue.attributes.declared import DeclaredAttribute
from django_glue.glue.attributes.definition import GlueAttributeKind, GlueValueRole
from django_glue.glue.attributes.registry import GlueAttributeRegistry
from django_glue.glue.children import GlueChildBinder
from django_glue.glue.context import GlueManifest
from django_glue.glue.loading import LoadingStrategy
from django_glue.glue.operation import GlueOperation, GlueOperationKind
from django_glue.glue.policy import GluePolicy
from django_glue.response import GlueResponse

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from django_glue.glue.attributes.definition import (
        BoundGlueAttribute,
        GlueAttributeDefinition,
    )
    from django_glue.glue.attributes.adapter import GlueAttributeAdapter
    from django_glue.glue.children import BoundGlueChild
    from django.http import JsonResponse
    from django_glue.resolver.attribute_call.context import AttributeCallRequestContext


class BaseGlue(ABC):
    """Native Glue runtime object that can serialize and handle attribute requests."""

    namespace: str

    def __init__(
        self,
        *,
        name: str | None = None,
        access: GlueAccess,
        loading_strategy: LoadingStrategy = LoadingStrategy.LAZY,
    ) -> None:
        self.name = name or self.namespace
        self.access = access
        self.loading_strategy = LoadingStrategy(loading_strategy)
        self.request: HttpRequest | None = None
        self._address: str | None = None

    @property
    def resolved_loading_strategy(self) -> LoadingStrategy:
        if self.loading_strategy == LoadingStrategy.INHERIT:
            return LoadingStrategy.LAZY
        return self.loading_strategy

    @property
    def is_bound(self) -> bool:
        """True if this glue object is bound to a request context."""
        return self.request is not None

    @cached_property
    def policy(self) -> GluePolicy:
        """Signed client-held policy for this request-bound Glue object."""
        if not self.is_bound:
            msg = (
                f"Cannot generate policy for unbound GlueObject '{self.name}'. "
                'Bind to a request first.'
            )
            raise RuntimeError(msg)

        return GluePolicy.from_glue_object(glue_object=self)

    @property
    def address(self) -> str:
        """The stable, opaque wire address for this object (state-model.md §10).

        Assigned at introduction or by the introducing owner's child binder. It is
        never derived from parameter values, so a parameter transition (e.g. a
        ``target_pk`` that advances after a save) does not rewrite it.
        """
        if self._address is None:
            self._address = self._derive_address()
        return self._address

    def _derive_address(self) -> str:
        return address.top_level(self.name, self.namespace)

    @property
    def manifest(self) -> GlueManifest:
        return GlueManifest(
            policy_token=self.policy.token,
            metadata=self.metadata,
            state=self.state if self.resolved_loading_strategy == LoadingStrategy.EAGER else {},
            loading_strategy=self.resolved_loading_strategy,
        )

    @cached_property
    def _attribute_registry(self) -> GlueAttributeRegistry:
        attribute_definitions, attribute_providers = self._collect_attributes()
        return GlueAttributeRegistry(
            attribute_definitions,
            attribute_providers=attribute_providers,
        )

    def _collect_attributes(
        self,
    ) -> tuple[tuple[GlueAttributeDefinition, ...], dict[str, Any]]:
        provider_definitions, provider_bindings = GlueAttributeCollector.collect_from_providers(
            self.get_attribute_providers()
        )
        extra_definitions, extra_bindings = GlueAttributeCollector.collect_extra_attributes(
            self.get_extra_attributes()
        )
        adapters = self.get_attribute_adapters()
        definitions = (
            GlueAttributeCollector.collect(type(self))
            + provider_definitions
            + extra_definitions
        )
        return (
            tuple(
                replace(definition, adapter=adapters.get(definition.path))
                if definition.kind == GlueAttributeKind.VALUE
                else definition
                for definition in definitions
            ),
            provider_bindings | extra_bindings,
        )

    @cached_property
    def _bound_attributes(self) -> dict[str, BoundGlueAttribute]:
        return {
            attribute.definition.path: attribute
            for attribute in self._attribute_registry.bind(self)
        }

    @cached_property
    def _bound_children(self) -> tuple[BoundGlueChild, ...]:
        return self._bind_children()

    @property
    def children(self) -> dict[str, str]:
        """Shallow signed map from canonical child paths to addresses (state-model.md §10).

        Carries no child policy or state; the child is an independently addressed,
        independently introduced object.
        """
        return {child.path: child.address for child in self._bound_children}

    def get_extra_attributes(
        self,
    ) -> Iterable[tuple[Any, Mapping[str, Any]]]:
        return ()

    def get_attribute_adapters(self) -> Mapping[str, GlueAttributeAdapter]:
        return {}

    def _bind_children(
        self,
        *,
        live_children: Mapping[str, str] | None = None,
        reintroduce: Iterable[str] = (),
    ) -> tuple[BoundGlueChild, ...]:
        return GlueChildBinder(
            self,
            self._attribute_registry,
        ).bind(
            live_children=live_children,
            reintroduce=reintroduce,
        )

    @property
    def attributes(self) -> dict[str, BoundGlueAttribute]:
        return self._bound_attributes

    @property
    def attribute_providers(self) -> Iterable[Any]:
        """Objects whose @Attribute-decorated attributes are exposed through this GlueObject."""
        return self.get_attribute_providers()

    def get_attribute_providers(self) -> Iterable[Any]:
        return ()

    def authorize(
        self,
        request: HttpRequest,
        operation: GlueOperation,
    ) -> bool:
        _ = request, operation
        return True

    def _require_authorization(self, operation: GlueOperation) -> None:
        if self.request is None:
            msg = f"Cannot authorize unbound Glue object '{self.name}'."
            raise RuntimeError(msg)

        if not self.authorize(self.request, operation):
            raise GlueAuthorizationError(
                object_name=self.name,
                operation=operation,
            )

    def _resolve_required_access(
        self,
        required_access: GlueAccess | Callable[[BaseGlue], GlueAccess],
    ) -> GlueAccess:
        """Resolve a declared required access against this glue object.

        A declaration may be a plain ``GlueAccess`` or a callable receiving
        the reconstructed glue object, so the required access can be chosen
        from the signed target identity (state-model.md §3) rather than from
        client input.
        """
        if callable(required_access):
            return required_access(self)
        return required_access

    @property
    def identity(self) -> dict[str, Any]:
        """
        Object-specific target identity for the policy.

        By default, auto-generates identity from attributes marked with
        identity=True (e.g., @Glue.property(identity=True) or
        @Glue.attr(required_access=..., identity=True)).

        Override in subclasses for custom behavior.
        """
        return self.get_identity()

    def get_identity(self) -> dict[str, Any]:
        return self._build_identity_from_attributes()

    def _build_identity_from_attributes(self) -> dict[str, Any]:
        """Build identity dict from collected identity attributes."""
        identity_data: dict[str, Any] = {}

        for path, attribute in self._bound_attributes.items():
            if not attribute.definition.is_identity:
                continue
            identity_data[path] = json.loads(
                json.dumps(attribute.get(), cls=GlueResponseJSONEncoder)
            )

        return identity_data

    @cached_property
    def state(self) -> dict[str, Any]:
        """Build mutable state from attributes."""
        return self.get_state()

    def get_state(self) -> dict[str, Any]:
        return {
            path: self._get_attribute_state(attribute)
            for path, attribute in self._bound_attributes.items()
            if attribute.definition.kind == GlueAttributeKind.VALUE
        }

    def _get_attribute_state(self, attribute: BoundGlueAttribute) -> Any:
        return {
            'value': attribute.get(),
            **attribute.unsigned_data(),
        }

    @cached_property
    def metadata(self) -> dict[str, Any]:
        """Build non-authoritative client metadata for target."""
        return self.get_metadata()

    def get_metadata(self) -> dict[str, Any]:
        return {
            'attributes': {
                path: self._get_attribute_metadata(attribute)
                for path, attribute in self._bound_attributes.items()
            },
        }

    def _get_attribute_metadata(
        self,
        attribute: BoundGlueAttribute,
    ) -> dict[str, Any]:
        definition = attribute.definition
        if definition.adapter is not None:
            return attribute.schema()
        if definition.kind == GlueAttributeKind.CALLABLE:
            return {
                'namespace': 'callable',
                'takes_client_state': True,
            }
        if definition.kind == GlueAttributeKind.NAMESPACE:
            return {'namespace': 'namespace'}
        if definition.kind == GlueAttributeKind.CHILD:
            return {'namespace': 'child'}
        return {'name': definition.path, 'namespace': 'readonly'}

    @classmethod
    def from_attribute_call_resolver_context(
        cls,
        context: AttributeCallRequestContext
    ) -> Self:
        glue_object = cls._reconstruct_from_policy(context.target_glue_policy)
        glue_object.request = context.request
        glue_object._address = context.target_glue_policy.address

        attribute = glue_object._bound_attributes.get(context.target_attribute_name)
        required_access = (
            glue_object._resolve_required_access(attribute.definition.required_access)
            if attribute is not None
            else GlueAccess.VIEW
        )
        glue_object._require_authorization(GlueOperation(
            kind=GlueOperationKind.CALL,
            attribute=None,
            required_access=required_access,
        ))

        return glue_object

    @classmethod
    @abstractmethod
    def _reconstruct_from_policy(cls, policy: GluePolicy) -> Self:
        """Reconstruct a GlueObject from a signed policy."""
        raise NotImplementedError

    def _load_client_state(self, state: dict[str, Any]) -> None:
        """Apply client-provided state attributes to this Glue object."""
        for path, attribute in self._bound_attributes.items():
            if attribute.definition.value_role != GlueValueRole.EDITABLE_STATE:
                continue
            if path not in state:
                continue

            attribute_state = state[path]
            value = (
                attribute_state.get('value')
                if isinstance(attribute_state, dict)
                else attribute_state
            )
            attribute.apply_update(value)

    def _invalidate_attributes(self) -> None:
        """Discard discovered attributes after target state hydration."""
        self.__dict__.pop('attributes', None)
        self.__dict__.pop('_attribute_registry', None)
        self.__dict__.pop('_bound_attributes', None)
        self.__dict__.pop('policy', None)
        self.__dict__.pop('metadata', None)
        self._invalidate_state()

    def _invalidate_state(self) -> None:
        self.__dict__.pop('state', None)

    @DeclaredAttribute(required_access=GlueAccess.VIEW, takes_client_state=False)
    def load_state(self) -> dict[str, Any]:
        return self.state

    def process_attribute_call(
        self,
        call_context: AttributeCallRequestContext
    ) -> JsonResponse:
        """Perform a callable attribute request against a resolved target."""
        bound_attribute = self._bound_attributes.get(call_context.target_attribute_name)
        if bound_attribute is None:
            raise GlueMissingAttributeError(call_context.target_attribute_name, self.name)

        definition = bound_attribute.definition
        if definition.kind != GlueAttributeKind.CALLABLE:
            raise GlueCalledStateAttributeError(call_context.target_attribute_name, self.name)

        required_access = self._resolve_required_access(definition.required_access)
        if not call_context.target_glue_policy.access.has_access(required_access):
            raise GlueAccessError(
                attribute=call_context.target_attribute_name,
                required_access=required_access.value,
                current_access=call_context.target_glue_policy.access.value,
            )

        signed_callable = call_context.target_glue_policy.capability.callables.get(
            call_context.target_attribute_name
        )
        if signed_callable is None:
            raise GlueMissingAttributeError(
                call_context.target_attribute_name,
                call_context.target_glue_policy.name
            )

        supplied_arguments = set(call_context.target_attribute_call_kwargs)
        admitted_arguments = (
            set(definition.allowed_arguments)
            & set(signed_callable.allowed_arguments)
        )
        invalid_arguments = supplied_arguments - admitted_arguments
        if invalid_arguments:
            raise GlueRequestError(
                code=GlueRequestErrorCode.INVALID_KWARGS,
                message='Callable arguments are not admitted by the signed capability.',
                details={
                    'attribute': definition.path,
                    'arguments': sorted(invalid_arguments),
                },
            )

        self._require_authorization(GlueOperation(
            kind=GlueOperationKind.CALL,
            attribute=call_context.target_attribute_name,
            required_access=required_access,
        ))

        self._load_client_state(call_context.target_glue_client_state or {})
        self._invalidate_attributes()
        bound_attribute = self._bound_attributes[call_context.target_attribute_name]
        call_result = bound_attribute.call(
            **self._resolve_callable_arguments(
                bound_attribute,
                call_context,
            )
        )

        return GlueResponse.from_result(
            call_result,
            render_as_html=definition.render_as_html,
        ).to_json_response(
            glue_object=self,
            policy_token=self.policy.token,
            state=self.state,
            metadata=self.metadata,
        )

    @staticmethod
    def _resolve_callable_arguments(
        attribute: BoundGlueAttribute,
        call_context: AttributeCallRequestContext,
    ) -> dict[str, Any]:
        target = attribute.get()
        signature = inspect.signature(inspect.unwrap(target))
        supplied = call_context.target_attribute_call_kwargs
        resolved: dict[str, Any] = {}

        for name, parameter in signature.parameters.items():
            if name in attribute.definition.injected_arguments:
                resolved[name] = call_context.request
            elif name in supplied:
                resolved[name] = supplied[name]
            elif parameter.kind in {
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            }:
                continue
            elif parameter.default is inspect.Parameter.empty:
                msg = (
                    f"Attribute '{attribute.definition.path}' missing required "
                    f"argument: '{name}'."
                )
                raise ValueError(msg)

        return resolved
