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
    GlueComponentRegistrationError,
    GlueMissingAttributeError,
    GlueRequestError,
    GlueRequestErrorCode,
)
from django_glue.glue import address
from django_glue.glue.attributes.collector import GlueAttributeCollector
from django_glue.glue.attributes.definition import GlueAttributeKind, GlueValueRole
from django_glue.glue.attributes.registry import GlueAttributeRegistry
from django_glue.glue.children import GlueChildBinder
from django_glue.glue.context import GlueObjectEntry
from django_glue.glue.event import GlueEvent
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
    from django_glue.resolver.attribute_call.context import AttributeCallRequestContext


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
        self._address: str | None = None
        self._derived_paths: set[str] = set()
        self._disposed = False
        self._pending_events: list[dict[str, Any]] = []

    @property
    def is_bound(self) -> bool:
        """True if this glue object is bound to a request context."""
        return self.request is not None

    def dispose(self) -> None:
        """Mark this object as authoritatively removed (state-model.md §6).

        The response to the current attribute call carries ``effects.dispose``
        for this address, and the client tears the proxy tree down.
        """
        self._disposed = True

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
    def entry(self) -> GlueObjectEntry:
        """A complete first snapshot (state-model.md §10 "Page load")."""
        return GlueObjectEntry(
            address=self.address,
            policy_token=self.policy.token,
            static_data=self.get_static_data(),
            computed_data=self.get_computed_data(include_all=True),
        )

    def _serialized_child_entries(self) -> list[dict[str, Any]]:
        serialized: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add_children(owner: BaseGlue) -> None:
            for child in owner._bound_children:
                if child.glue_object is None or child.address in seen:
                    continue

                seen.add(child.address)
                child.glue_object._address = child.address
                serialized.append(child.glue_object.entry.model_dump())
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

    def cap_access(self, ceiling: GlueAccess) -> None:
        """Lower this object's access to ``ceiling`` when it exceeds it
        (state-model.md §10: an introduced capability cannot exceed the
        caller's)."""
        if not ceiling.has_access(self.access):
            self.access = ceiling

    def introduce(self, request: HttpRequest) -> None:
        operation = GlueOperation(
            kind=GlueOperationKind.INTRODUCE,
            attribute=None,
            required_access=self.access,
        )
        if not self.authorize(request, operation):
            raise GlueAuthorizationError(object_name=self.name, operation=operation)
        self.request = request

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
        """Object-specific target identity for the policy. Families that
        reconstruct from configuration (model class, target PK, encoded
        query) override ``get_identity()``."""
        return self.get_identity()

    def get_identity(self) -> dict[str, Any]:
        return {}

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
                    'returns_glue': definition.expected_type is not None,
                }
        static_data: dict[str, Any] = {}
        if fields:
            static_data['fields'] = fields
        if children:
            static_data['children'] = children
        if callables:
            static_data['callables'] = callables
        declarations = [
            (name, declaration)
            for provider in (self, *self.get_attribute_providers())
            for name, declaration in inspect.getmembers_static(type(provider))
            if isinstance(declaration, GlueEvent)
        ]
        names = [name for name, _declaration in declarations]
        if len(names) != len(set(names)):
            raise GlueComponentRegistrationError('Glue event names must be unique on an address.')
        events = names
        if events:
            static_data['events'] = events
        forwarded_events = {
            name: declaration.from_child
            for name, declaration in declarations
            if declaration.from_child is not None
        }
        if forwarded_events:
            static_data['forwarded_events'] = forwarded_events
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
        if context.target_attribute_name is not None:
            kind = GlueOperationKind.CALL
        elif context.target_glue_updates:
            kind = GlueOperationKind.UPDATE
        else:
            kind = GlueOperationKind.REFRESH
        glue_object._require_authorization(GlueOperation(
            kind=kind,
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

    def _admit_reintroduce(self, policy: GluePolicy, reintroduce: list[str]) -> None:
        """Admission for a client-supplied ``reintroduce`` list (state-model.md
        §10 "Reintroducing an expired child"). Ordinary untrusted input: the
        only effect it can cause is running a slot factory the owner already
        declared, so a path that is not a declared child slot fails admission."""
        if not reintroduce:
            return
        declared = {
            attribute.definition.path
            for attribute in self._bound_attributes.values()
            if attribute.definition.kind is GlueAttributeKind.CHILD
        }
        unknown = [path for path in reintroduce if path not in declared]
        if unknown:
            raise GlueRequestError(
                code=GlueRequestErrorCode.INVALID_REINTRODUCE,
                message='reintroduce names a path that is not a declared child slot.',
                details={'paths': unknown},
            )

    def _refreshed_output(self) -> dict[str, Any]:
        """All downward output, re-derived for a refresh (state-model.md §6)."""
        return self.get_computed_data(include_all=True)

    def _refresh_entry(
        self,
        policy: GluePolicy,
        computed_data: dict[str, Any],
    ) -> dict[str, Any]:
        """The addressed entry of a call-less request — a refresh, optionally
        reintroducing children (state-model.md §6, §10): no result or effects,
        the omitted-when-unchanged token, and all downward output re-derived."""
        entry: dict[str, Any] = {'address': self.address}
        if not self._retained_values_equal(policy, self.policy):
            entry['policy_token'] = self.policy.token
        if computed_data:
            entry['computed_data'] = computed_data
        entry['result'] = None
        entry['effects'] = {'messages': []}
        return entry

    def _hydrate(self, policy: GluePolicy, raw_updates: Any) -> None:
        """Restore the token's canonical editable draft and apply the admitted
        client ``updates`` over it (state-model.md §5)."""
        updates = self._admit_updates(policy, raw_updates)
        for path in updates:
            self._require_authorization(GlueOperation(
                kind=GlueOperationKind.UPDATE,
                attribute=path,
                required_access=self._resolve_required_access(
                    self._bound_attributes[path].definition.required_access,
                ),
            ))
        retained_draft = {
            path: value
            for path, value in self._retained_draft(policy).items()
            if path not in updates
        }
        self._load_client_state({**retained_draft, **updates})
        self._invalidate_attributes()

    def _retained_draft(self, policy: GluePolicy) -> dict[str, Any]:
        """The acknowledged editable draft the verified token carries: every
        signed editable-state value."""
        return {
            path: attribute.decode_retained(policy.state_snapshot[path])
            for path, attribute in self._bound_attributes.items()
            if (
                attribute.definition.value_role == GlueValueRole.EDITABLE_STATE
                and path in policy.state_snapshot
            )
        }

    def _introduced_entries(
        self,
        policy: GluePolicy,
        reintroduce: list[str],
    ) -> list[dict[str, Any]]:
        """The children that ride this response: every child whose
        path/address binding changed, or — when the map is otherwise
        unchanged — exactly the children the request reintroduced at their
        existing addresses (state-model.md §10 slot-resolution table)."""
        if self.children != policy.children:
            return self._serialized_child_entries()
        if not reintroduce:
            return []
        reintroduced_addresses = {policy.children[path] for path in reintroduce}
        return [
            child_entry
            for child_entry in self._serialized_child_entries()
            if child_entry['address'] in reintroduced_addresses
        ]

    def process_attribute_call(
        self,
        call_context: AttributeCallRequestContext
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Perform a callable attribute request against a resolved target.

        Returns the addressed response entry (``address`` plus
        omitted-when-unchanged ``policy_token`` / ``static_data`` /
        ``computed_data``, ``result``, and ``effects``) and the entries of
        the children it newly introduced (state-model.md §10). A callable
        returning a Glue object has a wire ``result`` that is the object's
        address; its entry rides along when the object is not already a
        live or introduced child.

        Children bind against the incoming token's live set so a live,
        non-participating child carries forward without running its factory,
        and a child named in ``reintroduce`` is re-run at its existing
        address (state-model.md §10 slot-resolution table). Binding happens
        after the call runs, so children the call added or removed are
        reflected in the successor token.
        """
        policy = call_context.target_glue_policy
        self._admit_reintroduce(policy, call_context.reintroduce)

        if call_context.target_attribute_name is None:
            self._hydrate(policy, call_context.target_glue_updates)
            computed_data = self._refreshed_output()
            self.__dict__['_bound_children'] = self._bind_children(
                live_children=policy.children,
                reintroduce=call_context.reintroduce,
            )
            return (
                self._refresh_entry(policy, computed_data),
                self._introduced_entries(policy, call_context.reintroduce),
            )

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

        incoming_static_data = self.get_static_data()
        self._hydrate(policy, call_context.target_glue_updates)
        bound_attribute = self._bound_attributes[call_context.target_attribute_name]
        call_result = bound_attribute.call(
            **self._resolve_callable_arguments(
                bound_attribute,
                call_context,
            )
        )

        self.__dict__['_bound_children'] = self._bind_children(
            live_children=policy.children,
            reintroduce=call_context.reintroduce,
        )

        static_data = self.get_static_data()
        entry: dict[str, Any] = {'address': self.address}
        if not self._retained_values_equal(policy, self.policy):
            entry['policy_token'] = self.policy.token
        if static_data != incoming_static_data:
            entry['static_data'] = static_data
        computed_data = self.get_computed_data()
        if computed_data:
            entry['computed_data'] = computed_data

        introduced = self._introduced_entries(policy, call_context.reintroduce)

        response = GlueResponse.from_result(
            call_result,
            render_as_html=definition.render_as_html,
        )
        introduced.extend(response.objects)
        result = response.result
        if isinstance(result, BaseGlue):
            if (
                result.address not in policy.children.values()
                and result.address not in {
                    introduced_entry['address'] for introduced_entry in introduced
                }
            ):
                result._address = address.transient(self.address)
                result.cap_access(self.access)
                result.introduce(self.request)
                introduced.append(result.entry.model_dump())
                introduced.extend(result._serialized_child_entries())
            result = result.address
        else:
            GlueResponse._reject_glue_objects(result)
        entry['result'] = result
        if response.html is not None:
            entry['html'] = response.html
        entry['effects'] = self._effects_payload(response, introduced)
        return entry, introduced

    def _effects_payload(
        self,
        response: GlueResponse,
        introduced: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Build the response entry's ``effects`` channel (state-model.md §6).

        ``dispose`` carries the responding address when it was marked disposed,
        plus any owned addresses the callable named; naming an address the
        object does not own fails the entry. ``redirect`` and ``dispose`` are
        omitted when empty.
        """
        dispose = list(response.dispose or [])
        if self._disposed and self.address not in dispose:
            dispose.append(self.address)
        owned = {
            self.address,
            *self.children.values(),
            *(introduced_entry['address'] for introduced_entry in introduced),
        }
        unknown = [item for item in dispose if item not in owned]
        if unknown:
            raise GlueRequestError(
                code=GlueRequestErrorCode.INVALID_DISPOSE,
                message='effects.dispose names an address the responding object does not own.',
                details={'addresses': unknown},
            )
        effects: dict[str, Any] = {
            'messages': [message.to_dict() for message in response.messages],
        }
        if response.redirect is not None:
            effects['redirect'] = response.redirect
        if dispose:
            effects['dispose'] = dispose
        if self._pending_events:
            effects['events'] = self._pending_events
        return effects

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
