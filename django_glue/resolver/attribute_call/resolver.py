from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.http import JsonResponse
from pydantic import ValidationError

from django_glue.encoders import GlueResponseJSONEncoder
from django_glue.exceptions import (
    GlueError,
    GlueInvalidSessionError,
    GlueInvalidUserError,
    GlueRequestError,
    GlueRequestErrorCode,
)
from django_glue.glue import policy
from django_glue.glue.registry import glue_class_registry
from django_glue.resolver.attribute_call.context import (
    AddressedObjectEntry,
    AttributeCallBatchContext,
    AttributeCallContextFactory,
    AttributeCallRequestContext,
)
from django_glue.resolver.base import GlueResolver

if TYPE_CHECKING:
    from django.http import HttpRequest


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
        for entry in context.entries:
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
        requested_addresses = {entry.address for entry in context.entries}
        for entry in context.entries:
            for wire_entry in self._resolve_entry(context, entry):
                address = wire_entry.get('address')
                if address != entry.address and address in requested_addresses:
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
        )
        try:
            self._validate_session_and_user(context.request, decoded)
            glue_object = glue_class_registry.get_glue_class(decoded.namespace).from_attribute_call_resolver_context(
                call_context
            )
            entry_payload, introduced = glue_object.process_attribute_call(call_context)
        except GlueError as error:
            return [self._error_entry(entry, error)]

        return [entry_payload, *introduced]

    @staticmethod
    def _validate_session_and_user(request: HttpRequest, decoded: policy.GluePolicy) -> None:
        current_session_id = request.session.session_key
        if decoded.session_id != current_session_id:
            raise GlueInvalidSessionError(
                decoded.name,
                policy_session_id=decoded.session_id,
                current_session_id=current_session_id,
            )

        current_user_id = getattr(getattr(request, 'user', None), 'id', None)
        if decoded.request_user_id != current_user_id:
            raise GlueInvalidUserError(
                decoded.name,
                policy_user_id=decoded.request_user_id,
                current_user_id=current_user_id,
            )

    @staticmethod
    def _error_entry(entry: AddressedObjectEntry, error: GlueError) -> dict[str, Any]:
        return {
            'address': entry.address,
            'error': {'code': error.code, 'message': str(error)},
        }
