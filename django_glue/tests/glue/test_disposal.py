from __future__ import annotations

import re
from typing import Any

import pytest

from django_glue import Glue
from django_glue.access import GlueAccess
from django_glue.exceptions import GlueRequestError, GlueRequestErrorCode
from django_glue.glue.base import BaseGlue
from django_glue.glue.component import Component
from django_glue.glue.policy import GluePolicy
from django_glue.response import GlueResponse

from django_glue.tests.glue.test_callable_parameters import call_context


class DisposalProbeChildGlue(BaseGlue):
    namespace = 'disposalProbeChild'

    @classmethod
    def _reconstruct_from_policy(cls, policy: GluePolicy) -> DisposalProbeChildGlue:
        return cls(
            name=policy.name,
            access=policy.access,
        )


class DisposalProbeComponent(Component):
    namespace = 'disposalProbeComponent'
    template = 'glue_template_test.html'

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

    @classmethod
    def _reconstruct_from_policy(cls, policy: GluePolicy) -> DisposalProbeComponent:
        return cls(
            name=policy.name,
            access=policy.access,
        )

    @Glue.attr
    def mark_disposed(self) -> None:
        self.dispose()

    @Glue.attr
    def plain_call(self) -> str:
        return 'ok'

    @Glue.attr
    def dispose_unowned(self) -> None:
        return GlueResponse(dispose=['someone#else'])

    @Glue.attr
    def spawn(self) -> DisposalProbeChildGlue:
        return DisposalProbeChildGlue(access=GlueAccess.VIEW)


class ChildSlotOwnerComponent(DisposalProbeComponent):
    namespace = 'disposalChildSlotOwner'

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.child_value = DisposalProbeChildGlue(access=GlueAccess.VIEW)

    @Glue.property
    def child(self) -> DisposalProbeChildGlue:
        return self.child_value

    @Glue.attr
    def dispose_child(self) -> None:
        return GlueResponse(dispose=[self.policy.children['child']])

    @Glue.attr
    def redirect(self) -> None:
        return GlueResponse(redirect={'url': '/next'})


def test_model_delete_disposes_its_own_address(
    mock_request,
    db,
) -> None:
    from test_project.gorilla.models import Gorilla

    del db
    gorilla = Gorilla.objects.create(name='Doomed')
    model = Glue.model(
        request=mock_request,
        target=gorilla,
        unique_name='doomed_gorilla',
        access=GlueAccess.DELETE,
        fields=['id', 'name'],
    )

    context = call_context(model, 'delete')
    reconstructed = type(model).from_attribute_call_resolver_context(context)
    entry, introduced = reconstructed.process_attribute_call(context)

    assert Gorilla.objects.filter(pk=gorilla.pk).count() == 0
    assert entry['address'] == model.address
    assert entry['effects']['dispose'] == [model.address]
    assert introduced == []


def test_dispose_marker_disposes_responding_address(mock_request) -> None:
    component = Glue.object(mock_request, DisposalProbeComponent())

    context = call_context(component, 'mark_disposed')
    reconstructed = DisposalProbeComponent.from_attribute_call_resolver_context(context)
    entry, _ = reconstructed.process_attribute_call(context)

    assert entry['effects']['dispose'] == [component.address]


def test_effects_omit_dispose_and_redirect_when_unset(mock_request) -> None:
    component = Glue.object(mock_request, DisposalProbeComponent())

    context = call_context(component, 'plain_call')
    reconstructed = DisposalProbeComponent.from_attribute_call_resolver_context(context)
    entry, _ = reconstructed.process_attribute_call(context)

    assert entry['effects'] == {'messages': []}


def test_dispose_of_owned_child_address(mock_request) -> None:
    owner = Glue.object(mock_request, ChildSlotOwnerComponent())
    child_address = owner.policy.children['child']

    context = call_context(owner, 'dispose_child')
    reconstructed = ChildSlotOwnerComponent.from_attribute_call_resolver_context(context)
    entry, _ = reconstructed.process_attribute_call(context)

    assert entry['effects']['dispose'] == [child_address]


def test_dispose_of_unowned_address_fails_entry(mock_request) -> None:
    component = Glue.object(mock_request, DisposalProbeComponent())

    context = call_context(component, 'dispose_unowned')
    reconstructed = DisposalProbeComponent.from_attribute_call_resolver_context(context)

    with pytest.raises(GlueRequestError) as excinfo:
        reconstructed.process_attribute_call(context)

    assert excinfo.value.code == GlueRequestErrorCode.INVALID_DISPOSE
    assert excinfo.value.details() == {'addresses': ['someone#else']}


def test_redirect_effect_rides_effects_channel(mock_request) -> None:
    owner = Glue.object(mock_request, ChildSlotOwnerComponent())

    context = call_context(owner, 'redirect')
    reconstructed = ChildSlotOwnerComponent.from_attribute_call_resolver_context(context)
    entry, _ = reconstructed.process_attribute_call(context)

    assert entry['result'] is None
    assert entry['effects']['redirect'] == {'url': '/next'}
    assert 'dispose' not in entry['effects']


def test_call_result_is_minted_as_transient_address_beneath_owner(mock_request) -> None:
    component = Glue.object(mock_request, DisposalProbeComponent())

    context = call_context(component, 'spawn')
    reconstructed = DisposalProbeComponent.from_attribute_call_resolver_context(context)
    entry, introduced = reconstructed.process_attribute_call(context)

    result_address = entry['result']
    assert re.fullmatch(
        re.escape(component.address) + r'\["t[0-9a-f]{16}"\]',
        result_address,
    )
    assert len(introduced) == 1
    assert introduced[0]['address'] == result_address
    child_policy = GluePolicy.from_token(introduced[0]['policy_token'])
    assert child_policy.address == result_address
    assert child_policy.namespace == 'disposalProbeChild'
    assert child_policy.children == {}
    assert 'policy_token' not in entry


def test_repeated_spawns_mint_distinct_addresses(mock_request) -> None:
    component = Glue.object(mock_request, DisposalProbeComponent())

    minted: list[str] = []
    for _ in range(2):
        context = call_context(component, 'spawn')
        reconstructed = DisposalProbeComponent.from_attribute_call_resolver_context(context)
        entry, _ = reconstructed.process_attribute_call(context)
        minted.append(entry['result'])

    assert minted[0] != minted[1]


def test_spawn_does_not_grow_owner_children_map(mock_request) -> None:
    component = Glue.object(mock_request, DisposalProbeComponent())
    policy = component.policy

    context = call_context(component, 'spawn')
    reconstructed = DisposalProbeComponent.from_attribute_call_resolver_context(context)
    entry, introduced = reconstructed.process_attribute_call(context)

    assert entry['result'] not in policy.children.values()
    assert all(item['address'] != policy.address for item in introduced)
    assert reconstructed.policy.children == policy.children
    assert 'policy_token' not in entry
