from __future__ import annotations

import inspect
import json
from abc import ABC, abstractmethod
from dataclasses import replace
from functools import cached_property
from typing import TYPE_CHECKING, Any, Callable, Self

from django.http import HttpRequest

from django_glue.access import GlueAccess
from django_glue.conf import settings as glue_settings
from django_glue.encoders import GlueResponseJSONEncoder
from django_glue.exceptions import (
    GlueAccessError,
    GlueAuthorizationError,
    GlueCalledNonCallableAttributeError,
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
from django_glue.serialization import GlueSerializerError

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
        self._derived_paths: set[str] = set()

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
        static_data = self.get_static_data()
        computed_data = (
            self.get_computed_data(include_all=True)
            if self.resolved_loading_strategy == LoadingStrategy.EAGER
            else {}
        )
        return GlueManifest(
            address=self.address,
            policy_token=self.policy.token,
            static_data=static_data,
            computed_data=computed_data,
            loading_strategy=self.resolved_loading_strategy,
        )

    def _serialized_child_manifests(self) -> list[dict[str, Any]]:
        serialized: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add_children(owner: BaseGlue) -> None:
            for child in owner._bound_children:
                if child.glue_object is None or child.address in seen:
                    continue
                seen.add(child.address)
                child.glue_object._address = child.address
                serialized.append(child.glue_object.manifest.model_dump())
                add_children(child.glue_object)

        add_children(self)
        return serialized

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
            **attribute.computed_data(),
        }

    def get_static_data(self) -> dict[str, Any]:
        """Client-visible static data (state-model.md §10 "Responses omit what
        did not change"): field descriptors with ``value_path`` state-path
        mappings, addressed-child kind/nullable slots, and callable argument
        shapes. Down-only and client-forgets: stable across calls for an
        unchanged object, omitted from the response when it did not change,
        and never sent back to the server."""
        fields: dict[str, Any] = {}
        children: dict[str, Any] = {}
        callables: dict[str, Any] = {}
        for path, attribute in self._bound_attributes.items():
            definition = attribute.definition
            if definition.kind is GlueAttributeKind.VALUE:
                if definition.adapter is None:
                    fields[path] = {
                        'value_path': path,
                        'editable': definition.value_role is GlueValueRole.EDITABLE_STATE,
                    }
                else:
                    fields[path] = attribute.schema()
            elif definition.kind is GlueAttributeKind.CHILD:
                children[path] = {
                    'kind': definition.expected_type.namespace,
                    'nullable': definition.is_nullable,
                }
            elif definition.kind is GlueAttributeKind.CALLABLE:
                callables[path] = {
                    'allowed_arguments': list(definition.allowed_arguments),
                }
        static_data: dict[str, Any] = {}
        if fields:
            static_data['fields'] = fields
        if children:
            static_data['children'] = children
        if callables:
            static_data['callables'] = callables
        return static_data

    def get_computed_data(self, *, include_all: bool = False) -> dict[str, Any]:
        """Complete current down-only output (state-model.md §5, §10):
        re-derived values at top level, and re-derived adapter output under
        ``fields``.

        Only output re-derived this request is included — "an adapter that
        did not re-derive its downward output omits the key entirely," so
        omission means the client's previous value stands. ``include_all``
        is the introduction surface, where every value is fresh by
        construction.
        """
        computed: dict[str, Any] = {}
        fields_output: dict[str, Any] = {}
        for path, attribute in self._bound_attributes.items():
            definition = attribute.definition
            if definition.kind is not GlueAttributeKind.VALUE:
                continue
            if definition.value_role is GlueValueRole.DERIVED_OUTPUT:
                if include_all or path in self._derived_paths:
                    computed[path] = attribute.get()
            elif definition.adapter is not None:
                if include_all or path in self._derived_paths:
                    adapter_output = attribute.computed_data()
                    if adapter_output:
                        fields_output[path] = adapter_output
        if fields_output:
            computed['fields'] = fields_output
        return computed

    @staticmethod
    def _retained_values_equal(
        incoming: GluePolicy,
        successor: GluePolicy,
    ) -> bool:
        """Whether the successor's retained values match the verified incoming
        token (state-model.md §10 "Responses omit what did not change").

        ``created_at`` is temporal and ``token`` is the signature over the
        rest, so both are excluded; the subject fields stay in the comparison
        — they are constant for a verified request, so any divergence there
        means the token must be reissued. Values are normalized through the
        library's own encoder, matching how identity data is round-tripped.
        """
        exclude = {'created_at', 'token'}
        incoming_dump = json.loads(
            json.dumps(incoming.model_dump(exclude=exclude), cls=GlueResponseJSONEncoder)
        )
        successor_dump = json.loads(
            json.dumps(successor.model_dump(exclude=exclude), cls=GlueResponseJSONEncoder)
        )
        return incoming_dump == successor_dump

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

    def _retained_state(self) -> dict[str, Any]:
        """Non-parameterized retained state signed into the successor policy
        token's ``state_snapshot``: internal reconstructors plus the family's
        acknowledged editable state (state-model.md §5, §10)."""
        retained: dict[str, Any] = {}
        for path, attribute in self._bound_attributes.items():
            definition = attribute.definition
            if (
                definition.kind is GlueAttributeKind.VALUE
                and definition.value_role is GlueValueRole.RECONSTRUCTOR
            ):
                retained[path] = attribute.get()
        return retained

    def _admit_updates(
        self,
        policy: GluePolicy,
        updates: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Protocol admission for client updates (state-model.md §10, stage 1).

        Checks the current declaration, the signed capability, payload shape
        and resource limits. A violation fails the request before the action
        runs, so no successor token is issued.
        """
        if not updates:
            return {}
        if not isinstance(updates, dict):
            raise GlueRequestError(
                code=GlueRequestErrorCode.INVALID_UPDATES,
                message='"updates" must be a JSON object.',
            )
        if len(updates) > glue_settings.DJANGO_GLUE_MAX_UPDATES:
            raise GlueRequestError(
                code=GlueRequestErrorCode.INVALID_UPDATES,
                message='Too many updates in one request.',
                details={'limit': glue_settings.DJANGO_GLUE_MAX_UPDATES},
            )
        if len(json.dumps(updates).encode('utf-8')) > glue_settings.DJANGO_GLUE_MAX_UPDATES_ENCODED_BYTES:
            raise GlueRequestError(
                code=GlueRequestErrorCode.INVALID_UPDATES,
                message='Updates exceed the encoded size limit.',
                details={'limit': glue_settings.DJANGO_GLUE_MAX_UPDATES_ENCODED_BYTES},
            )

        signed_attributes = {
            entry for entry in policy.attributes if isinstance(entry, str)
        }
        admitted: dict[str, Any] = {}
        for path, value in updates.items():
            attribute = self._bound_attributes.get(path)
            if attribute is None:
                raise GlueRequestError(
                    code=GlueRequestErrorCode.INVALID_UPDATES,
                    message='Update targets an unknown attribute.',
                    details={'attribute': path},
                )
            definition = attribute.definition
            if (
                definition.kind != GlueAttributeKind.VALUE
                or definition.value_role != GlueValueRole.EDITABLE_STATE
            ):
                raise GlueRequestError(
                    code=GlueRequestErrorCode.INVALID_UPDATES,
                    message='Update targets a non-editable attribute.',
                    details={'attribute': path},
                )
            if path not in signed_attributes:
                raise GlueRequestError(
                    code=GlueRequestErrorCode.INVALID_UPDATES,
                    message='Update is not admitted by the signed capability.',
                    details={'attribute': path},
                )
            try:
                admitted[path] = attribute.coerce_update(value)
            except GlueSerializerError as error:
                raise GlueRequestError(
                    code=GlueRequestErrorCode.INVALID_UPDATES,
                    message='Update value could not be coerced.',
                    details={'attribute': path},
                ) from error
        return admitted

    def _load_client_state(self, state: dict[str, Any]) -> None:
        """Apply retained state (signed snapshot plus admitted updates) to this
        Glue object (state-model.md §10)."""
        for path, attribute in self._bound_attributes.items():
            if attribute.definition.value_role != GlueValueRole.EDITABLE_STATE:
                continue
            if path not in state:
                continue
            attribute.apply_update(state[path])
            self._derived_paths.add(path)

    def _invalidate_attributes(self) -> None:
        """Discard discovered attributes after target state hydration."""
        self.__dict__.pop('attributes', None)
        self.__dict__.pop('_attribute_registry', None)
        self.__dict__.pop('_bound_attributes', None)
        self.__dict__.pop('policy', None)
        self._invalidate_state()

    def _invalidate_state(self) -> None:
        self.__dict__.pop('state', None)

    @DeclaredAttribute(required_access=GlueAccess.VIEW)
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
            raise GlueCalledNonCallableAttributeError(call_context.target_attribute_name, self.name)

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

        policy = call_context.target_glue_policy
        incoming_static_data = self.get_static_data()
        updates = self._admit_updates(policy, call_context.target_glue_updates)
        retained_state = {
            path: attribute.decode_retained(policy.state_snapshot[path])
            for path, attribute in self._bound_attributes.items()
            if (
                attribute.definition.value_role == GlueValueRole.EDITABLE_STATE
                and path in policy.state_snapshot
                and path not in updates
            )
        }
        self._load_client_state({**retained_state, **updates})
        self._invalidate_attributes()
        bound_attribute = self._bound_attributes[call_context.target_attribute_name]
        call_result = bound_attribute.call(
            **self._resolve_callable_arguments(
                bound_attribute,
                call_context,
            )
        )

        static_data = self.get_static_data()
        payload: dict[str, Any] = {}
        if not self._retained_values_equal(policy, self.policy):
            payload['policy_token'] = self.policy.token
        if static_data != incoming_static_data:
            payload['static_data'] = static_data
        computed_data = self.get_computed_data()
        if computed_data:
            payload['computed_data'] = computed_data
        if self.children != policy.children:
            manifest_list = self._serialized_child_manifests()
            if manifest_list:
                payload['manifest_list'] = manifest_list

        return GlueResponse.from_result(
            call_result,
            render_as_html=definition.render_as_html,
        ).to_json_response(
            glue_object=self,
            **payload,
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
