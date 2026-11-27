from __future__ import annotations

import json
from typing import Any

from django.http import HttpRequest
from django.urls import ResolverMatch
from django.utils.datastructures import MultiValueDict
from pydantic import BaseModel, Field, ValidationError

from django_glue.conf import settings as glue_settings
from django_glue.exceptions import GlueRequestError, GlueRequestErrorCode
from django_glue.glue import policy
from django_glue.glue.operation import GlueOperationKind


class AttributeCall(BaseModel):
    attribute: str
    kwargs: dict[str, Any] = Field(default_factory=dict)


class ReceiverEntry(BaseModel):
    """
    A mounted object a request entry names as reacting to an event the entry's
    object declares (ADR 044). It is untrusted: the server answers it only for
    an event the call emitted that the receiver's class reacts to, through the
    same checks as a requested entry.
    """

    address: str
    policy_token: str
    updates: dict[str, Any] = Field(default_factory=dict)
    mounted: list[str] = Field(default_factory=list)
    child_submissions: dict[str, Any] = Field(default_factory=dict)


class AddressedObjectEntry(BaseModel):
    """One addressed object in the ``objects`` request envelope
    (state-model.md §10).

    ``call`` is optional: a reintroduction request names the owner and the
    canonical child paths to re-sign and carries no call (state-model.md
    §10 "Reintroducing an expired child").

    ``mounted`` lists the component roots the client has inside a
    component's root. A render keeps them instead of re-stamping them
    (ADR 025). It is untrusted: a client that lists a child it does not have
    only denies itself that child's markup.

    ``child_submissions`` carries, by slot path, the signed token and unsaved
    changes of each child a component declares with ``Glue.child``. It is
    untrusted, and is only read when the call reads that child.

    ``receivers`` names the mounted objects that would react to an event the
    entry's object declares; the events its call emits reach them in the same
    response (ADR 044)."""

    address: str
    policy_token: str
    updates: dict[str, Any] = Field(default_factory=dict)
    call: AttributeCall | None = None
    reintroduce: list[str] = Field(default_factory=list)
    mounted: list[str] = Field(default_factory=list)
    child_submissions: dict[str, Any] = Field(default_factory=dict)
    receivers: list[ReceiverEntry] = Field(default_factory=list)


class AttributeCallRequestContext(BaseModel):
    """Per-entry context: one reconstructed object and its single call."""

    model_config = {'arbitrary_types_allowed': True}

    request: HttpRequest
    target_glue_policy: policy.GluePolicy
    target_glue_updates: dict[str, Any] = Field(default_factory=dict)
    target_attribute_name: str | None = None
    target_attribute_call_kwargs: dict[str, Any] = Field(default_factory=dict)
    reintroduce: list[str] = Field(default_factory=list)
    mounted: list[str] = Field(default_factory=list)
    child_submissions: dict[str, Any] = Field(default_factory=dict)
    file_prefix: str = ''
    allow_uploaded_files: bool = True
    suppressed_file_children: frozenset[str] = Field(default_factory=frozenset)

    @property
    def uploaded_files(self) -> MultiValueDict[str, Any]:
        """The uploaded files scoped to this entry, keyed by bare field name."""
        if not self.allow_uploaded_files:
            return MultiValueDict()
        if not self.file_prefix:
            return self.request.FILES

        prefix = self.file_prefix
        return MultiValueDict({
            key.removeprefix(prefix): self.request.FILES.getlist(key)
            for key in self.request.FILES
            if key.startswith(prefix)
        })

    def for_child_submission(
        self,
        *,
        path: str,
        child_policy: policy.GluePolicy,
        updates: dict[str, Any],
    ) -> AttributeCallRequestContext:
        """Build a scoped call context for a submitted ``@Glue.child`` slot."""
        return AttributeCallRequestContext.model_construct(
            request=self.request,
            target_glue_policy=child_policy,
            target_glue_updates=updates,
            target_attribute_name=None,
            file_prefix=f'child_submissions.{path}.',
            allow_uploaded_files=self.allow_uploaded_files and path not in self.suppressed_file_children,
            suppressed_file_children=frozenset(),
        )

    def for_formset_row(
        self,
        *,
        row_key: str,
        row_policy: policy.GluePolicy,
        updates: dict[str, Any],
    ) -> AttributeCallRequestContext:
        """Build a scoped call context for one row form inside a formset."""
        return AttributeCallRequestContext.model_construct(
            request=self.request,
            target_glue_policy=row_policy,
            target_glue_updates=updates,
            file_prefix=f'{self.file_prefix}forms.{row_key}.' if self.file_prefix else '',
            allow_uploaded_files=self.allow_uploaded_files,
            suppressed_file_children=frozenset(),
        )

    @property
    def operation_kind(self) -> GlueOperationKind:
        """The interaction this entry asks for: a call, an update, or a refresh."""
        if self.target_attribute_name is not None:
            return GlueOperationKind.CALL
        if self.target_glue_updates:
            return GlueOperationKind.UPDATE
        return GlueOperationKind.REFRESH


class AttributeCallBatchContext(BaseModel):
    model_config = {'arbitrary_types_allowed': True}

    request: HttpRequest
    entries: list[AddressedObjectEntry]
    # Each origin is resolved once per request, however many entries share it.
    resolved_origins: dict[str, ResolverMatch] = Field(default_factory=dict)


class AttributeCallContextFactory:
    """Parses and validates the request envelope.

    Envelope faults (malformed ``objects``, empty batch, duplicate
    addresses) fail the whole request. Address-scoped faults — a policy
    that does not decode, an outer address that disagrees with its signed
    policy — are the resolver's to report per entry, because the other
    entries in the batch still travel.
    """

    def __init__(self, request: HttpRequest) -> None:
        self.request = request

    def create(self) -> AttributeCallBatchContext:
        self._validate_content_type()
        return AttributeCallBatchContext(
            request=self.request,
            entries=self._validated_entries,
        )

    @property
    def _validated_entries(self) -> list[AddressedObjectEntry]:
        if 'objects' not in self.request.POST:
            raise GlueRequestError(
                code=GlueRequestErrorCode.MISSING_FIELD,
                message='objects is required',
                details={'field': 'objects'},
            )

        try:
            parsed = json.loads(self.request.POST.get('objects', ''))
        # RecursionError: a deeply nested body is malformed input, not a server error.
        except (TypeError, ValueError, RecursionError) as error:
            raise GlueRequestError(
                code=GlueRequestErrorCode.INVALID_JSON,
                message='objects is not valid JSON.',
                details={'field': 'objects'},
            ) from error

        if not isinstance(parsed, list) or not parsed:
            raise GlueRequestError(
                code=GlueRequestErrorCode.MALFORMED_REQUEST,
                message='objects must be a non-empty list of addressed entries.',
                details={'field': 'objects'},
            )

        entries = []
        for item in parsed:
            try:
                entry = AddressedObjectEntry.model_validate(item)
            except ValidationError as error:
                raise GlueRequestError(
                    code=GlueRequestErrorCode.MALFORMED_REQUEST,
                    message='Each objects entry needs an address and a policy_token.',
                    details={'field': 'objects', 'errors': error.errors()},
                ) from error
            entries.append(entry)

        addresses = [
            address
            for entry in entries
            for address in (entry.address, *(receiver.address for receiver in entry.receivers))
        ]
        # Each address is an object to rebuild, authorize and answer.
        limit = glue_settings.DJANGO_GLUE_MAX_REQUEST_ADDRESSES
        if len(addresses) > limit:
            raise GlueRequestError(
                code=GlueRequestErrorCode.TOO_MANY_ADDRESSES,
                message='Too many objects in one request.',
                details={'field': 'objects', 'limit': limit},
            )
        if len(addresses) != len(set(addresses)):
            raise GlueRequestError(
                code=GlueRequestErrorCode.DUPLICATE_ADDRESSES,
                message='objects addresses must be unique within a request.',
                details={'field': 'objects'},
            )

        return entries

    def _validate_content_type(self) -> None:
        content_type = self.request.content_type or ''
        if not content_type.startswith('multipart/form-data'):
            raise GlueRequestError(
                code=GlueRequestErrorCode.INVALID_CONTENT_TYPE,
                message='Glue requests must be sent as multipart/form-data.',
                details={'content_type': content_type},
            )
