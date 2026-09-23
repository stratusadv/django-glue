import json
from typing import Any

from django.http import HttpRequest
from pydantic import BaseModel, Field, ValidationError

from django_glue.exceptions import GlueRequestError, GlueRequestErrorCode
from django_glue.glue import policy


class AttributeCall(BaseModel):
    attribute: str
    kwargs: dict[str, Any] = Field(default_factory=dict)


class AddressedObjectEntry(BaseModel):
    """One addressed object in the ``objects`` request envelope
    (state-model.md §10).

    ``call`` is optional: a reintroduction request names the owner and the
    canonical child paths to re-sign and carries no call (state-model.md
    §10 "Reintroducing an expired child")."""

    address: str
    policy_token: str
    updates: dict[str, Any] = Field(default_factory=dict)
    call: AttributeCall | None = None
    reintroduce: list[str] = Field(default_factory=list)


class AttributeCallRequestContext(BaseModel):
    """Per-entry context: one reconstructed object and its single call."""

    model_config = {'arbitrary_types_allowed': True}

    request: HttpRequest
    target_glue_policy: policy.GluePolicy
    target_glue_updates: dict[str, Any] = Field(default_factory=dict)
    target_attribute_name: str | None = None
    target_attribute_call_kwargs: dict[str, Any] = Field(default_factory=dict)
    reintroduce: list[str] = Field(default_factory=list)


class AttributeCallBatchContext(BaseModel):
    model_config = {'arbitrary_types_allowed': True}

    request: HttpRequest
    entries: list[AddressedObjectEntry]


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
        except (TypeError, ValueError) as error:
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

        addresses = [entry.address for entry in entries]
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
