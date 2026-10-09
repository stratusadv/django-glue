from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect
from django.template import Context, Template
from django.utils.decorators import method_decorator

from django_glue import Glue, GlueAccess, GlueOperation, GlueOperationKind
from django_glue.exceptions import GlueAuthorizationError
from django_glue.glue.base import BaseGlue
from django_glue.glue.components import component_registry
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


class AnsweringGlue(BaseGlue):
    namespace = 'answering'

    def __init__(self, answer: Any) -> None:
        super().__init__(name='answering', access=GlueAccess.VIEW)
        self.answer = answer

    def is_authorized(self, request: HttpRequest, operation: GlueOperation) -> Any:
        _ = request, operation
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer

    @classmethod
    def _reconstruct_from_policy(cls, _policy: GluePolicy) -> AnsweringGlue:
        return cls(True)


def test_a_response_from_is_authorized_is_a_denial_that_keeps_the_response(
    mock_request: HttpRequest,
) -> None:
    redirect = HttpResponseRedirect('/login/')

    with pytest.raises(GlueAuthorizationError) as error:
        GlueContextManager(mock_request).add_glue(AnsweringGlue(redirect))

    assert error.value.response is redirect


def test_permission_denied_raised_by_is_authorized_is_a_denial(
    mock_request: HttpRequest,
) -> None:
    with pytest.raises(GlueAuthorizationError) as error:
        GlueContextManager(mock_request).add_glue(AnsweringGlue(PermissionDenied()))

    assert error.value.response is None


def test_false_from_is_authorized_is_a_denial_without_a_response(
    mock_request: HttpRequest,
) -> None:
    with pytest.raises(GlueAuthorizationError) as error:
        GlueContextManager(mock_request).add_glue(AnsweringGlue(False))

    assert error.value.response is None


@pytest.mark.parametrize('answer', [1, 'yes', None, object()])
def test_an_answer_that_is_not_a_boolean_or_a_response_is_refused(
    mock_request: HttpRequest,
    answer: Any,
) -> None:
    with pytest.raises(TypeError, match=r'AnsweringGlue\.is_authorized\(\) must return'):
        GlueContextManager(mock_request).add_glue(AnsweringGlue(answer))


class LoginRequiredCardComponent(Glue.Component):
    template = 'glue_template_test.html'

    @method_decorator(login_required)
    def is_authorized(self, request: HttpRequest, operation: GlueOperation) -> bool:
        _ = request, operation
        return True

    @Glue.attr
    def touch(self) -> None:
        pass


class PermissionRequiredCardComponent(Glue.Component):
    template = 'glue_template_test.html'

    @method_decorator(permission_required('gorilla.view_gorilla', raise_exception=True))
    def is_authorized(self, request: HttpRequest, operation: GlueOperation) -> bool:
        _ = request, operation
        return True


def test_a_decorated_is_authorized_redirects_an_anonymous_page_load(
    mock_request: HttpRequest,
) -> None:
    mock_request.user = AnonymousUser()

    response = LoginRequiredCardComponent.as_view()(mock_request)

    assert response.status_code == 302
    assert response['Location'] == '/accounts/login/?next=/'


def test_a_decorated_is_authorized_serves_the_page_to_a_signed_in_user(
    mock_request: HttpRequest,
    db: None,
) -> None:
    mock_request.user = get_user_model().objects.create_user(username='decorated-view-user')

    response = LoginRequiredCardComponent.as_view()(mock_request)

    assert response.status_code == 200


def test_a_decorator_that_raises_makes_the_page_load_forbidden(
    mock_request: HttpRequest,
) -> None:
    mock_request.user = AnonymousUser()

    with pytest.raises(PermissionDenied):
        PermissionRequiredCardComponent.as_view()(mock_request)


def test_a_decorated_is_authorized_denies_a_stamp(mock_request: HttpRequest) -> None:
    mock_request.user = AnonymousUser()
    component_registry.by_tag_name['login_required_card'] = LoginRequiredCardComponent

    try:
        html = Template(
            "{% load django_glue %}{% glue_component 'login_required_card' %}"
        ).render(Context({'request': mock_request}))
    finally:
        del component_registry.by_tag_name['login_required_card']

    assert html == ''
    assert GlueContextManager(mock_request).serialized_objects == []


def test_a_decorated_is_authorized_denies_a_later_call(
    mock_request: HttpRequest,
    db: None,
) -> None:
    mock_request.user = get_user_model().objects.create_user(username='decorated-call-user')
    component = GlueContextManager(mock_request).add_glue(LoginRequiredCardComponent())
    context = AttributeCallRequestContext(
        request=mock_request,
        target_glue_policy=component.policy,
        target_glue_updates={},
        target_attribute_name='touch',
    )
    mock_request.user = AnonymousUser()

    with pytest.raises(GlueAuthorizationError):
        LoginRequiredCardComponent.from_attribute_call_resolver_context(context)
