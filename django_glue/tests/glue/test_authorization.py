from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from django_glue import Glue, GlueAccess, GlueOperation, GlueOperationKind
from django_glue.exceptions import GlueAuthorizationError
from django_glue.glue.base import BaseGlue
from django_glue.glue.context import GlueContextManager
from django_glue.resolver.attribute_call.context import AttributeCallRequestContext

if TYPE_CHECKING:
    from django.http import HttpRequest

    from django_glue.glue.policy import GluePolicy


class AuthorizationProbeGlue(BaseGlue):
    namespace = 'authorizationProbe'

    value = Glue.attr('canonical')

    def __init__(
        self,
        *,
        name: str = 'authorization-probe',
        access: GlueAccess = GlueAccess.CHANGE,
    ) -> None:
        super().__init__(
            name=name,
            access=access,
        )
        self.call_count = 0

    def is_authorized(
        self,
        request: HttpRequest,
        operation: GlueOperation,
    ) -> bool:
        request.authorization_operations.append((operation, self.value))
        return (
            request.authorization_allowed
            and operation.attribute not in request.denied_attributes
        )

    @Glue.attr(required_access=GlueAccess.CHANGE)
    def change(self) -> str:
        self.call_count += 1
        return self.value

    @classmethod
    def _reconstruct_from_policy(
        cls,
        policy: GluePolicy,
    ) -> AuthorizationProbeGlue:
        return cls(
            name=policy.name,
            access=policy.access,
        )


class PermissiveGlue(BaseGlue):
    namespace = 'permissive'

    def __init__(self) -> None:
        super().__init__(access=GlueAccess.VIEW)

    @classmethod
    def _reconstruct_from_policy(cls, _policy: GluePolicy) -> PermissiveGlue:
        return cls()


def prepare_request(request: HttpRequest) -> None:
    request.authorization_allowed = True
    request.authorization_operations = []
    request.denied_attributes = set()


def attribute_call_context(
    request: HttpRequest,
    policy: GluePolicy,
    *,
    updates: dict[str, Any] | None = None,
) -> AttributeCallRequestContext:
    return AttributeCallRequestContext(
        request=request,
        target_glue_policy=policy,
        target_glue_updates=updates or {},
        target_attribute_name='change',
    )


def test_default_authorization_is_permissive(
    mock_request: HttpRequest,
) -> None:
    glue = PermissiveGlue()

    assert glue.is_authorized(
        mock_request,
        GlueOperation(
            kind=GlueOperationKind.INTRODUCE,
            attribute=None,
            required_access=GlueAccess.VIEW,
        ),
    )


def test_introduction_authorizes_requested_capability(
    mock_request: HttpRequest,
) -> None:
    prepare_request(mock_request)
    glue = AuthorizationProbeGlue(access=GlueAccess.CHANGE)

    GlueContextManager(mock_request).add_glue(glue)

    assert mock_request.authorization_operations == [(
        GlueOperation(
            kind=GlueOperationKind.INTRODUCE,
            attribute=None,
            required_access=GlueAccess.CHANGE,
        ),
        'canonical',
    )]


def test_introduction_denial_does_not_register_object(
    mock_request: HttpRequest,
) -> None:
    prepare_request(mock_request)
    mock_request.authorization_allowed = False
    manager = GlueContextManager(mock_request)

    with pytest.raises(GlueAuthorizationError) as error:
        manager.add_glue(AuthorizationProbeGlue())

    assert error.value.code == 'not_authorized'
    assert manager.glue_objects == []


def test_reconstruction_denial_precedes_client_state_hydration(
    mock_request: HttpRequest,
) -> None:
    prepare_request(mock_request)
    glue = GlueContextManager(mock_request).add_glue(AuthorizationProbeGlue())
    policy = glue.policy
    mock_request.authorization_operations.clear()
    mock_request.authorization_allowed = False
    context = attribute_call_context(
        mock_request,
        policy,
        updates={'value': 'untrusted'},
    )

    with pytest.raises(GlueAuthorizationError):
        AuthorizationProbeGlue.from_attribute_call_resolver_context(context)

    assert mock_request.authorization_operations == [(
        GlueOperation(
            kind=GlueOperationKind.CALL,
            attribute=None,
            required_access=GlueAccess.CHANGE,
        ),
        'canonical',
    )]


def test_attribute_denial_blocks_call_without_issuing_successor_policy(
    mock_request: HttpRequest,
) -> None:
    prepare_request(mock_request)
    glue = GlueContextManager(mock_request).add_glue(AuthorizationProbeGlue())
    context = attribute_call_context(
        mock_request,
        glue.policy,
        updates={'value': 'untrusted'},
    )
    mock_request.authorization_operations.clear()
    mock_request.denied_attributes.add('change')
    reconstructed = AuthorizationProbeGlue.from_attribute_call_resolver_context(context)

    with pytest.raises(GlueAuthorizationError) as error:
        reconstructed.process_attribute_call(context)

    assert error.value.details() == {
        'object': 'authorization-probe',
        'kind': 'call',
        'attribute': 'change',
        'required_access': 'change',
    }
    assert reconstructed.call_count == 0
    assert reconstructed.value == 'canonical'
    assert 'policy' not in reconstructed.__dict__
