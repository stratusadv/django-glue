from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from django_glue import Glue
from django_glue.access import GlueAccess
from django_glue.exceptions import GlueRequestError
from django_glue.glue.base import BaseGlue
from django_glue.glue.objects.django.model.object import ModelGlue
from django_glue.glue.policy import GluePolicy
from django_glue.resolver.attribute_call.context import AttributeCallRequestContext

if TYPE_CHECKING:
    from django.http import HttpRequest


class CallableProbeGlue(BaseGlue):
    namespace = 'callableProbe'

    value = Glue.attr('canonical', editable=True)

    def __init__(self) -> None:
        super().__init__(access=GlueAccess.CHANGE)

    @Glue.attr
    def process(
        self,
        request: HttpRequest,
        step: int = 1,
        **_kwargs: Any,
    ) -> dict[str, Any]:
        return {
            'request_is_bound': request is self.request,
            'step': step,
            'value': self.value,
        }

    @Glue.attr
    def required(self, volume: int) -> int:
        return volume

    @classmethod
    def _reconstruct_from_policy(cls, policy: GluePolicy) -> CallableProbeGlue:
        _ = policy
        return cls()


class CallableProvider:
    def __init__(self, target: NamespacedCallableGlue) -> None:
        self.target = target

    @Glue.attr
    def echo(
        self,
        request: HttpRequest,
        suffix: str = '!',
    ) -> str:
        assert request is self.target.request
        return f'{self.target.value}{suffix}'


class NamespacedCallableGlue(BaseGlue):
    namespace = 'namespacedCallable'

    services = Glue.namespace(CallableProvider)

    def __init__(self) -> None:
        super().__init__(access=GlueAccess.VIEW)
        self.value = 'echo'

    @classmethod
    def _reconstruct_from_policy(
        cls,
        policy: GluePolicy,
    ) -> NamespacedCallableGlue:
        _ = policy
        return cls()


class CallableChildGlue(BaseGlue):
    namespace = 'callableChild'

    def __init__(self) -> None:
        super().__init__(access=GlueAccess.VIEW)

    @classmethod
    def _reconstruct_from_policy(
        cls,
        policy: GluePolicy,
    ) -> CallableChildGlue:
        _ = policy
        return cls()


class OtherCallableChildGlue(BaseGlue):
    namespace = 'otherCallableChild'

    def __init__(self) -> None:
        super().__init__(access=GlueAccess.VIEW)

    @classmethod
    def _reconstruct_from_policy(
        cls,
        policy: GluePolicy,
    ) -> OtherCallableChildGlue:
        _ = policy
        return cls()


class CallableResultGlue(BaseGlue):
    namespace = 'callableResult'

    def __init__(self) -> None:
        super().__init__(access=GlueAccess.VIEW)

    @Glue.attr
    def child(self) -> CallableChildGlue:
        return CallableChildGlue()

    @Glue.attr
    def optional_child(self) -> CallableChildGlue | None:
        return None

    @Glue.attr
    def ordinary_result(self) -> object:
        return CallableChildGlue()

    @Glue.attr
    def nested_in_dict(self) -> dict:
        return {'child': CallableChildGlue()}

    @Glue.attr
    def nested_in_list(self) -> list:
        return [CallableChildGlue()]

    @Glue.attr
    def wrong_child_family(self) -> CallableChildGlue:
        return OtherCallableChildGlue()

    @Glue.attr
    def missing_child(self) -> CallableChildGlue:
        return None

    @Glue.attr
    def bound_child(self) -> CallableChildGlue:
        child = CallableChildGlue()
        child.request = self.request
        return child

    @classmethod
    def _reconstruct_from_policy(
        cls,
        policy: GluePolicy,
    ) -> CallableResultGlue:
        _ = policy
        return cls()


class IssuingGlue(BaseGlue):
    namespace = 'issuing'

    def __init__(self, access: GlueAccess = GlueAccess.VIEW, issued_access: GlueAccess = GlueAccess.DELETE) -> None:
        super().__init__(access=access)
        self.issued_access = issued_access

    @Glue.attr
    def issue_model(self) -> ModelGlue:
        from test_project.gorilla.models import Gorilla  # noqa: PLC0415

        return ModelGlue(
            Gorilla.objects.get(name='Issued'),
            name='issued',
            access=self.issued_access,
            fields=['name', 'age'],
        )

    @classmethod
    def _reconstruct_from_policy(cls, policy: GluePolicy) -> IssuingGlue:
        return cls(access=policy.access)


def call_context(
    glue_object: BaseGlue,
    attribute: str | None,
    *,
    kwargs: dict[str, Any] | None = None,
    updates: dict[str, Any] | None = None,
    reintroduce: list[str] | None = None,
) -> AttributeCallRequestContext:
    assert glue_object.request is not None
    return AttributeCallRequestContext.model_construct(
        request=glue_object.request,
        target_glue_policy=glue_object.policy,
        target_glue_updates=updates or {},
        target_attribute_name=attribute,
        target_attribute_call_kwargs=kwargs or {},
        reintroduce=reintroduce or [],
    )


def test_policy_signs_declared_client_arguments_only(
    mock_request: HttpRequest,
) -> None:
    glue_object = Glue.object(
        mock_request,
        CallableProbeGlue(),
    )

    process = glue_object.policy.capability.callables['process']
    definition = glue_object._attribute_registry.get('process')

    assert process.allowed_arguments == ('step',)
    assert definition is not None
    assert definition.injected_arguments == ('request',)


def test_call_injects_request_and_applies_editable_updates(
    mock_request: HttpRequest,
) -> None:
    glue_object = Glue.object(
        mock_request,
        CallableProbeGlue(),
    )
    context = call_context(
        glue_object,
        'process',
        kwargs={'step': 2},
        updates={'value': 'draft'},
    )

    payload, _introduced = glue_object.process_attribute_call(context)

    assert payload['result'] == {
        'request_is_bound': True,
        'step': 2,
        'value': 'draft',
    }


def test_variadic_keyword_parameter_does_not_open_capability(
    mock_request: HttpRequest,
) -> None:
    glue_object = Glue.object(
        mock_request,
        CallableProbeGlue(),
    )
    context = call_context(
        glue_object,
        'process',
        kwargs={'extra': 'untrusted'},
    )

    with pytest.raises(GlueRequestError) as error:
        glue_object.process_attribute_call(context)

    assert error.value.code == 'invalid_kwargs'
    assert error.value.details()['arguments'] == ['extra']


def test_client_cannot_supply_injected_request(
    mock_request: HttpRequest,
) -> None:
    glue_object = Glue.object(
        mock_request,
        CallableProbeGlue(),
    )
    context = call_context(
        glue_object,
        'process',
        kwargs={'request': 'untrusted'},
    )

    with pytest.raises(GlueRequestError) as error:
        glue_object.process_attribute_call(context)

    assert error.value.details()['arguments'] == ['request']


def test_missing_required_parameter_raises(
    mock_request: HttpRequest,
) -> None:
    glue_object = Glue.object(
        mock_request,
        CallableProbeGlue(),
    )
    context = call_context(
        glue_object,
        'required',
    )

    with pytest.raises(ValueError, match="missing required argument: 'volume'"):
        glue_object.process_attribute_call(context)


def test_dotted_namespace_call_uses_bound_provider(
    mock_request: HttpRequest,
) -> None:
    glue_object = Glue.object(
        mock_request,
        NamespacedCallableGlue(),
    )
    context = call_context(
        glue_object,
        'services.echo',
        kwargs={'suffix': '?'},
    )

    payload, _introduced = glue_object.process_attribute_call(context)

    assert payload['result'] == 'echo?'


def test_declared_glue_callable_result_is_the_introduced_address(
    mock_request: HttpRequest,
) -> None:
    glue_object = Glue.object(
        mock_request,
        CallableResultGlue(),
    )

    entry, introduced = glue_object.process_attribute_call(
        call_context(glue_object, 'child')
    )
    introduction = next(
        introduced_entry
        for introduced_entry in introduced
        if introduced_entry['address'] == entry['result']
    )
    result_policy = GluePolicy.from_token(introduction['policy_token'])

    assert isinstance(entry['result'], str)
    assert result_policy.namespace == 'callableChild'


def test_nullable_glue_callable_result_accepts_none(
    mock_request: HttpRequest,
) -> None:
    glue_object = Glue.object(
        mock_request,
        CallableResultGlue(),
    )

    entry, introduced = glue_object.process_attribute_call(
        call_context(glue_object, 'optional_child')
    )

    assert entry['result'] is None
    assert introduced == []


def test_glue_callable_result_requires_annotation(
    mock_request: HttpRequest,
) -> None:
    glue_object = Glue.object(
        mock_request,
        CallableResultGlue(),
    )

    with pytest.raises(TypeError, match='without a Glue-object return annotation'):
        glue_object.process_attribute_call(
            call_context(glue_object, 'ordinary_result')
        )


@pytest.mark.parametrize('attribute', ['nested_in_dict', 'nested_in_list'])
def test_callable_result_rejects_nested_glue_objects(
    mock_request: HttpRequest,
    attribute: str,
) -> None:
    glue_object = Glue.object(
        mock_request,
        CallableResultGlue(),
    )

    with pytest.raises(TypeError, match='return it directly as the result'):
        glue_object.process_attribute_call(
            call_context(glue_object, attribute)
        )


def test_glue_callable_result_rejects_wrong_family(
    mock_request: HttpRequest,
) -> None:
    glue_object = Glue.object(
        mock_request,
        CallableResultGlue(),
    )

    with pytest.raises(TypeError, match='must return an unbound CallableChildGlue'):
        glue_object.process_attribute_call(
            call_context(glue_object, 'wrong_child_family')
        )


def test_glue_callable_result_rejects_none_when_not_nullable(
    mock_request: HttpRequest,
) -> None:
    glue_object = Glue.object(
        mock_request,
        CallableResultGlue(),
    )

    with pytest.raises(TypeError, match='Non-nullable Glue callable'):
        glue_object.process_attribute_call(
            call_context(glue_object, 'missing_child')
        )


def test_glue_callable_result_rejects_bound_object(
    mock_request: HttpRequest,
) -> None:
    glue_object = Glue.object(
        mock_request,
        CallableResultGlue(),
    )

    with pytest.raises(ValueError, match='returned a bound Glue object'):
        glue_object.process_attribute_call(
            call_context(glue_object, 'bound_child')
        )


def test_reserved_request_name_rejects_conflicting_annotation() -> None:
    class InvalidCallableGlue(BaseGlue):
        namespace = 'invalidCallable'

        def __init__(self) -> None:
            super().__init__(access=GlueAccess.VIEW)

        @Glue.attr
        def invalid(self, request: str) -> None:
            return None

        @classmethod
        def _reconstruct_from_policy(
            cls,
            policy: GluePolicy,
        ) -> InvalidCallableGlue:
            _ = policy
            return cls()

    with pytest.raises(TypeError, match="reserves argument 'request'"):
        _ = InvalidCallableGlue()._attribute_registry


def _issued_policy(mock_request: HttpRequest, caller_access: GlueAccess, issued_access: GlueAccess) -> GluePolicy:
    from test_project.gorilla.models import Gorilla  # noqa: PLC0415

    Gorilla.objects.create(name='Issued')
    caller = Glue.object(mock_request, IssuingGlue(access=caller_access, issued_access=issued_access))
    entry, introduced = caller.process_attribute_call(call_context(caller, 'issue_model'))
    issued = next(item for item in introduced if item['address'] == entry['result'])
    return GluePolicy.from_token(issued['policy_token'])


def test_callable_result_capability_is_capped_to_the_caller(mock_request: HttpRequest, db) -> None:
    del db
    issued = _issued_policy(mock_request, GlueAccess.VIEW, GlueAccess.DELETE)

    assert issued.access == GlueAccess.VIEW
    assert list(issued.identity['editable']) == []


def test_callable_result_capability_is_never_raised_to_the_caller(mock_request: HttpRequest, db) -> None:
    del db
    issued = _issued_policy(mock_request, GlueAccess.DELETE, GlueAccess.VIEW)

    assert issued.access == GlueAccess.VIEW
