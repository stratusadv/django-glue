from __future__ import annotations

import json
from typing import Any

import pytest
from django.http import HttpRequest
from django.test import RequestFactory

from django_glue import Glue
from django_glue.exceptions import (
    GlueAccessError,
    GlueComponentRegistrationError,
    GlueInvalidPolicyError,
    GlueRequestError,
)
from django_glue.glue.context import GlueContextManager
from django_glue.glue.policy import GluePolicy
from django_glue.resolver.attribute_call.context import (
    AddressedObjectEntry,
    AttributeCall,
    AttributeCallBatchContext,
)
from django_glue.resolver.attribute_call.resolver import GlueAttributeCallResolver
from django_glue.tests.glue.test_callable_parameters import call_context
from test_project.gorilla.components import (
    CounterCardComponent,
    CounterDashboardComponent,
    CounterTallyComponent,
    GuardedCounterTallyComponent,
    QuietCounterTallyComponent,
    RerenderingCounterDashboardComponent,
)

COUNTED = CounterCardComponent.counted.identity


def _stamped(mock_request, component_class=CounterTallyComponent) -> tuple[Any, list[dict[str, Any]]]:
    """Render a component that stamps counter cards; return it and the cards' entries."""
    tally = Glue.object(mock_request, component_class())
    tally.render()
    cards = [
        entry
        for entry in GlueContextManager(mock_request).serialized_objects
        if GluePolicy.from_token(entry['policy_token']).identity.get('component_id', '').endswith(
            '.CounterCardComponent'
        )
    ]
    return tally, cards


def _next_request(mock_request) -> HttpRequest:
    """A later request in the same session, as the client's ``$receive`` is."""
    request = RequestFactory().post('/__dg__/callable_attribute/')
    request.session = mock_request.session
    return request


def _receive(tally: CounterTallyComponent, events: list[dict[str, Any]]) -> dict[str, Any]:
    context = call_context(tally, '$receive', kwargs={'events': events})
    context.request = _next_request(tally.request)
    reconstructed = type(tally).from_attribute_call_resolver_context(context)
    entry, _introduced = reconstructed.process_attribute_call(context)
    return entry


def _counted_from(card: dict[str, Any], **detail: Any) -> dict[str, Any]:
    return {'event': COUNTED, 'source_token': card['policy_token'], 'detail': detail}


def test_a_stamped_child_signs_its_ancestor_chain(mock_request) -> None:
    tally, cards = _stamped(mock_request)

    assert len(cards) == 2
    for card in cards:
        assert GluePolicy.from_token(card['policy_token']).identity['ancestors'] == [tally.address]


def test_static_data_publishes_emitted_and_listened_event_identities(mock_request) -> None:
    tally, cards = _stamped(mock_request)

    assert tally.get_static_data()['listeners'] == [COUNTED]
    assert cards[0]['static_data']['event_ids'] == {'counted': COUNTED}


def test_receive_runs_every_matching_listener_and_rerenders(mock_request) -> None:
    tally, cards = _stamped(mock_request)
    five = next(card for card in cards if GluePolicy.from_token(card['policy_token']).identity['parameters']['start'] == 5)

    entry = _receive(tally, [_counted_from(five, value=6)])

    snapshot = GluePolicy.from_token(entry['policy_token']).state_snapshot
    assert snapshot['last_counted_start'] == 5
    assert snapshot['counted_since_mount'] == 1
    assert 'Last counted 5, 1 counts' in entry['html']
    assert entry['result'] is None


def test_receive_delivers_several_events_and_renders_once(mock_request) -> None:
    tally, cards = _stamped(mock_request)

    entry = _receive(tally, [_counted_from(cards[0]), _counted_from(cards[1])])

    assert GluePolicy.from_token(entry['policy_token']).state_snapshot['counted_since_mount'] == 2
    assert entry['html'].count('data-testid="tally-summary"') == 1


def test_skip_rerender_listeners_that_change_nothing_do_not_render(mock_request) -> None:
    tally, cards = _stamped(mock_request, QuietCounterTallyComponent)

    entry = _receive(tally, [_counted_from(cards[0])])

    assert 'html' not in entry
    assert 'policy_token' not in entry


def test_rerender_on_rerenders_without_a_listener(mock_request) -> None:
    dashboard, cards = _stamped(mock_request, RerenderingCounterDashboardComponent)

    entry = _receive(dashboard, [_counted_from(cards[0])])

    assert dashboard.get_static_data()['listeners'] == [COUNTED]
    assert 'data-testid="counter-dashboard"' in entry['html']
    assert 'policy_token' not in entry


def test_rerender_on_takes_a_tuple_of_declared_events() -> None:
    with pytest.raises(TypeError, match='rerender_on takes one or more events'):
        class NameListedComponent(Glue.Component):
            template = 'glue_template_test.html'
            rerender_on = ('counted',)

    with pytest.raises(TypeError, match='rerender_on takes one or more events'):
        class UnwrappedComponent(Glue.Component):
            template = 'glue_template_test.html'
            rerender_on = CounterCardComponent.counted


def test_receive_rejects_an_event_the_component_does_not_handle(mock_request) -> None:
    dashboard, cards = _stamped(mock_request, CounterDashboardComponent)

    with pytest.raises(GlueRequestError, match='neither re-renders on nor listens for'):
        _receive(dashboard, [_counted_from(cards[0])])


def test_receive_rejects_a_source_that_is_not_a_descendant(mock_request) -> None:
    tally, _cards = _stamped(mock_request)
    stranger = Glue.object(mock_request, CounterCardComponent(start=1))

    with pytest.raises(GlueRequestError, match='not a descendant'):
        _receive(tally, [{'event': COUNTED, 'source_token': stranger.policy.token, 'detail': {}}])


def test_receive_rejects_an_event_the_source_does_not_declare(mock_request) -> None:
    tally, cards = _stamped(mock_request)

    with pytest.raises(GlueRequestError, match='does not declare'):
        _receive(tally, [{**_counted_from(cards[0]), 'event': 'test_project.gorilla.components.Other.counted'}])


def test_receive_rejects_a_forged_source_token(mock_request) -> None:
    tally, cards = _stamped(mock_request)

    with pytest.raises(GlueInvalidPolicyError):
        _receive(tally, [{**_counted_from(cards[0]), 'source_token': cards[0]['policy_token'] + 'x'}])


def test_receive_rejects_malformed_arguments(mock_request) -> None:
    tally, _cards = _stamped(mock_request)

    with pytest.raises(GlueRequestError, match='non-empty "events" list'):
        _receive(tally, [])


def test_listener_required_access_is_enforced(mock_request) -> None:
    tally, cards = _stamped(mock_request, GuardedCounterTallyComponent)

    with pytest.raises(GlueAccessError):
        _receive(tally, [_counted_from(cards[0])])


def test_a_component_returned_by_a_callable_signs_its_owner_as_ancestor(mock_request) -> None:
    tally = Glue.object(mock_request, CounterTallyComponent())
    context = call_context(tally, 'open_card')
    reconstructed = CounterTallyComponent.from_attribute_call_resolver_context(context)

    entry, introduced = reconstructed.process_attribute_call(context)

    card = next(item for item in introduced if item['address'] == entry['result'])
    assert GluePolicy.from_token(card['policy_token']).identity['ancestors'] == [tally.address]


def test_receive_travels_the_ordinary_call_endpoint(mock_request) -> None:
    tally, cards = _stamped(mock_request)
    context = AttributeCallBatchContext.model_construct(
        request=_next_request(mock_request),
        entries=[
            AddressedObjectEntry(
                address=tally.address,
                policy_token=tally.policy.token,
                call=AttributeCall(attribute='$receive', kwargs={'events': [_counted_from(cards[0])]}),
            ),
        ],
    )

    response = GlueAttributeCallResolver()._resolve_json_response_from_context(context)

    [entry, *_children] = json.loads(response.content)['objects']
    assert 'error' not in entry
    assert 'data-testid="counter-tally"' in entry['html']


def test_listener_must_be_declared_on_a_component() -> None:
    with pytest.raises(RuntimeError) as raised:
        class NotAComponent:
            @Glue.listener(CounterCardComponent.counted)
            def heard(self) -> None:
                pass

    assert isinstance(raised.value.__cause__, GlueComponentRegistrationError)


def test_listener_takes_declared_events_only() -> None:
    with pytest.raises(TypeError, match='declared on a class'):
        Glue.listener('counted')
