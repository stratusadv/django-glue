from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django.db import transaction
from django.http import JsonResponse
from pydantic import ValidationError

from django_glue.encoders import GlueResponseJSONEncoder
from django_glue.exceptions import (
    GlueError,
    GlueRequestError,
    GlueRequestErrorCode,
)
from django_glue.glue import policy
from django_glue.glue.event import RECEIVE_ATTRIBUTE, declared_event_identities
from django_glue.glue.registry import glue_class_registry
from django_glue.middleware.call import run_glue_call_hooks
from django_glue.resolver.attribute_call.context import (
    AddressedObjectEntry,
    AttributeCall,
    AttributeCallBatchContext,
    AttributeCallContextFactory,
    AttributeCallRequestContext,
    ReceiverEntry,
)
from django_glue.resolver.base import GlueResolver
from django_glue.response import GlueResponse

if TYPE_CHECKING:
    from django.http import HttpRequest


logger = logging.getLogger(__name__)


class GlueAttributeCallResolver(GlueResolver[AttributeCallBatchContext]):
    def _create_context_from_request(
        self,
        request: HttpRequest,
    ) -> AttributeCallBatchContext:
        context = AttributeCallContextFactory(request).create()
        self._validate_envelope(context)
        return context

    def _validate_envelope(self, context: AttributeCallBatchContext) -> None:
        """An outer address that disagrees with its signed policy makes the
        whole request uninterpretable (state-model.md §10); an undecodable
        policy is an address fault the entry reports on its own."""
        if context.request.FILES and any(
            entry.call is not None
            or entry.updates
            or entry.child_submissions
            or entry.receivers
            for entry in context.entries[1:]
        ):
            raise GlueRequestError(
                code=GlueRequestErrorCode.MALFORMED_REQUEST,
                message='A request with uploaded files may only carry companion refreshes alongside its primary entry.',
                details={'field': 'objects'},
            )

        receivers = [receiver for entry in context.entries for receiver in entry.receivers]
        for entry in [*context.entries, *receivers]:
            try:
                decoded = policy.GluePolicy.from_token(entry.policy_token)
            except (GlueError, ValidationError):
                continue
            if decoded.address != entry.address:
                raise GlueRequestError(
                    code=GlueRequestErrorCode.ADDRESS_MISMATCH,
                    message='Entry address does not match its signed policy.',
                    details={
                        'address': entry.address,
                        'policy_address': decoded.address,
                    },
                )

    def _resolve_json_response_from_context(
        self,
        context: AttributeCallBatchContext,
    ) -> JsonResponse:
        objects: list[dict[str, Any]] = []
        seen: set[str] = set()
        requested_addresses = {
            address
            for entry in context.entries
            for address in (entry.address, *(receiver.address for receiver in entry.receivers))
        }
        for index, entry in enumerate(context.entries):
            resolved = self._resolve_entry(
                context,
                entry,
                allow_uploaded_files=index == 0,
            )
            answered = [(entry.address, resolved)]
            if entry.receivers and 'error' not in resolved[0]:
                answered.extend(self._resolve_receivers(context, entry, resolved[0]))
            for answered_address, wire_entries in answered:
                for wire_entry in wire_entries:
                    address = wire_entry.get('address')
                    if address != answered_address and address in requested_addresses:
                        continue
                    if address in seen:
                        continue
                    if address is not None:
                        seen.add(address)
                    objects.append(wire_entry)
        return JsonResponse(
            {'objects': objects},
            status=200,
            encoder=GlueResponseJSONEncoder,
        )

    def _resolve_entry(
        self,
        context: AttributeCallBatchContext,
        entry: AddressedObjectEntry,
        *,
        allow_uploaded_files: bool = True,
    ) -> list[dict[str, Any]]:
        """Resolve one addressed entry. Address faults become an error entry
        and advance nothing; a success returns the addressed entry plus the
        children it newly introduced."""
        try:
            decoded = policy.GluePolicy.from_token(entry.policy_token)
        except (GlueError, ValidationError) as error:
            return [self._error_entry(entry, error)]

        call_context = AttributeCallRequestContext(
            request=context.request,
            target_glue_policy=decoded,
            target_glue_updates=entry.updates,
            target_attribute_name=entry.call.attribute if entry.call else None,
            target_attribute_call_kwargs=entry.call.kwargs if entry.call else {},
            reintroduce=entry.reintroduce,
            mounted=entry.mounted,
            child_submissions=entry.child_submissions,
            allow_uploaded_files=allow_uploaded_files,
        )
        try:
            decoded.verify_request(context.request)
            run_glue_call_hooks(call_context, context.resolved_origins)
            glue_object = glue_class_registry.get_glue_class(decoded.namespace).from_attribute_call_resolver_context(
                call_context
            )
            entry_payload, introduced = glue_object.process_attribute_call(call_context)
        except GlueError as error:
            return [self._error_entry(entry, error)]

        return [entry_payload, *introduced]

    def _resolve_receivers(
        self,
        context: AttributeCallBatchContext,
        entry: AddressedObjectEntry,
        answer: dict[str, Any],
    ) -> list[tuple[str, list[dict[str, Any]]]]:
        """
        Deliver the events ``entry``'s call emitted to the receivers it named
        that react to them, in this response (ADR 044). The events, and the
        token they came from, are the call's own. Each receiver is then
        resolved as a requested ``$receive`` entry is, in its own savepoint, so
        a receiver that fails leaves the call and what it wrote standing.
        """
        emitted = answer.get('effects', {}).get('events') or []
        if not emitted:
            return []

        source_token = answer.get('policy_token', entry.policy_token)
        source_policy = policy.GluePolicy.from_token(source_token)
        source_class = glue_class_registry.get_glue_class(source_policy.namespace)
        identities = declared_event_identities(*source_class.event_declaring_classes(source_policy))
        deliveries = [
            {
                'event': identities[event['name']],
                'source_token': source_token,
                'detail': event['detail'],
            }
            for event in emitted
            if event['name'] in identities
        ]

        answered = []
        for receiver in entry.receivers:
            try:
                with transaction.atomic():
                    wire_entries = self._resolve_receiver(
                        context,
                        receiver,
                        source_policy,
                        deliveries,
                    )
            except Exception:
                logger.exception('A receiver of %s failed.', entry.address)
                wire_entries = [self._error_entry(receiver, GlueError('The receiver failed.'))]
            if wire_entries:
                answered.append((receiver.address, wire_entries))
        return answered

    def _resolve_receiver(
        self,
        context: AttributeCallBatchContext,
        receiver: ReceiverEntry,
        source_policy: policy.GluePolicy,
        deliveries: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """A receiver's ``$receive`` answer, or nothing when it reacts to none of the deliveries."""
        try:
            receiver_policy = policy.GluePolicy.from_token(receiver.policy_token)
        except GlueError as error:
            return [self._error_entry(receiver, error)]

        receiver_class = glue_class_registry.get_glue_class(receiver_policy.namespace)
        reacting = set(receiver_class.reacting_events(
            receiver_policy,
            source_policy,
            [delivery['event'] for delivery in deliveries],
        ))
        if not reacting:
            return []

        events = [delivery for delivery in deliveries if delivery['event'] in reacting]
        return self._resolve_entry(
            context,
            AddressedObjectEntry(
                address=receiver.address,
                policy_token=receiver.policy_token,
                updates=receiver.updates,
                call=AttributeCall(attribute=RECEIVE_ATTRIBUTE, kwargs={'events': events}),
                mounted=receiver.mounted,
                child_submissions=receiver.child_submissions,
            ),
            allow_uploaded_files=False,
        )

    @staticmethod
    def _error_entry(
        entry: AddressedObjectEntry | ReceiverEntry,
        error: GlueError,
    ) -> dict[str, Any]:
        return {
            'address': entry.address,
            'error': GlueResponse.error_data(error),
        }
