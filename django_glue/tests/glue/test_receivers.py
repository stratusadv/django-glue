"""A call's receivers are answered in its own response (ADR 044)."""
from __future__ import annotations

import json
from typing import Any

import pytest
from django.http import HttpRequest
from django.test import RequestFactory

from django_glue import Glue, GlueOperation, GlueOperationKind
from django_glue.glue.policy import GluePolicy
from django_glue.resolver.attribute_call.context import (
    AddressedObjectEntry,
    AttributeCall,
    AttributeCallBatchContext,
    ReceiverEntry,
)
from django_glue.resolver.attribute_call.resolver import GlueAttributeCallResolver
from django_glue.tests.conftest import MockSession
from test_project.gorilla.components import (
    CounterCardComponent,
    CounterDashboardComponent,
    CounterTallyComponent,
    RerenderingCounterDashboardComponent,
)
from test_project.gorilla.models import Gorilla

# Each receiver is answered in a savepoint of its own.
pytestmark = pytest.mark.django_db


class RefusingDashboardComponent(RerenderingCounterDashboardComponent):
    def is_authorized(self, request: HttpRequest, operation: GlueOperation) -> bool:
        return operation.kind is not GlueOperationKind.CALL


class FailingDashboardComponent(RerenderingCounterDashboardComponent):
    def _template_context(self) -> dict[str, Any]:
        Gorilla.objects.create(name='Written by a failing receiver')
        message = 'The receiver template broke.'
        raise RuntimeError(message)


def _next_request(mock_request: HttpRequest) -> HttpRequest:
    request = RequestFactory().post('/__dg__/callable_attribute/')
    request.session = mock_request.session
    return request


def _receiver(glue: Any) -> ReceiverEntry:
    return ReceiverEntry(address=glue.address, policy_token=glue.policy.token)


def _call(
    mock_request: HttpRequest,
    source: Any,
    attribute: str,
    receivers: list[ReceiverEntry],
) -> list[dict[str, Any]]:
    """Resolve one call on ``source`` naming ``receivers``; return the response's objects."""
    context = AttributeCallBatchContext.model_construct(
        request=_next_request(mock_request),
        entries=[
            AddressedObjectEntry(
                address=source.address,
                policy_token=source.policy.token,
                call=AttributeCall(attribute=attribute),
                receivers=receivers,
            ),
        ],
        resolved_origins={},
    )
    response = GlueAttributeCallResolver()._resolve_json_response_from_context(context)
    return json.loads(response.content)['objects']


def _answer(objects: list[dict[str, Any]], glue: Any) -> dict[str, Any] | None:
    return next((entry for entry in objects if entry.get('address') == glue.address), None)


def test_a_call_answers_the_receivers_of_the_event_it_emits(mock_request) -> None:
    card = Glue.object(mock_request, CounterCardComponent(start=1))
    dashboard = Glue.object(mock_request, RerenderingCounterDashboardComponent())

    objects = _call(mock_request, card, 'increment', [_receiver(dashboard)])

    assert objects[0]['address'] == card.address
    assert objects[0]['result'] == 2
    assert 'data-testid="counter-dashboard"' in _answer(objects, dashboard)['html']


def test_a_receiver_that_does_not_react_is_not_answered(mock_request) -> None:
    card = Glue.object(mock_request, CounterCardComponent(start=1))
    dashboard = Glue.object(mock_request, CounterDashboardComponent())

    objects = _call(mock_request, card, 'increment', [_receiver(dashboard)])

    assert _answer(objects, dashboard) is None


def test_a_call_that_emits_nothing_answers_no_receiver(mock_request) -> None:
    card = Glue.object(mock_request, CounterCardComponent(start=1))
    dashboard = Glue.object(mock_request, RerenderingCounterDashboardComponent())

    objects = _call(mock_request, card, 'render', [_receiver(dashboard)])

    assert _answer(objects, dashboard) is None


def test_a_listener_is_answered_for_its_descendant_only(mock_request) -> None:
    tally = Glue.object(mock_request, CounterTallyComponent())
    card = CounterCardComponent(start=5)
    card._ancestors = (tally.address,)
    descendant = Glue.object(mock_request, card)
    stranger = Glue.object(mock_request, CounterCardComponent(start=9))

    from_descendant = _call(mock_request, descendant, 'increment', [_receiver(tally)])
    from_stranger = _call(mock_request, stranger, 'increment', [_receiver(tally)])

    answer = _answer(from_descendant, tally)
    assert GluePolicy.from_token(answer['policy_token']).state_snapshot['last_counted_start'] == 5
    assert _answer(from_stranger, tally) is None


def test_a_receiver_with_a_forged_token_is_answered_with_an_error(mock_request) -> None:
    card = Glue.object(mock_request, CounterCardComponent(start=1))
    dashboard = Glue.object(mock_request, RerenderingCounterDashboardComponent())
    payload, timestamp, _signature = dashboard.policy.token.split(':')
    forged = ReceiverEntry(address=dashboard.address, policy_token=f'{payload}:{timestamp}:forged')

    objects = _call(mock_request, card, 'increment', [forged])

    assert _answer(objects, dashboard)['error']['code'] == 'proxy_policy_invalid'
    assert 'error' not in objects[0]


def test_a_receiver_issued_to_another_session_is_answered_with_an_error(mock_request) -> None:
    card = Glue.object(mock_request, CounterCardComponent(start=1))
    elsewhere = RequestFactory().get('/')
    elsewhere.session = MockSession(session_key='another-session')
    dashboard = Glue.object(elsewhere, RerenderingCounterDashboardComponent())

    objects = _call(mock_request, card, 'increment', [_receiver(dashboard)])

    assert _answer(objects, dashboard)['error']['code'] == 'proxy_invalid_session'


def test_a_receiver_its_is_authorized_refuses_is_answered_with_an_error(mock_request) -> None:
    card = Glue.object(mock_request, CounterCardComponent(start=1))
    dashboard = Glue.object(mock_request, RefusingDashboardComponent())

    objects = _call(mock_request, card, 'increment', [_receiver(dashboard)])

    assert _answer(objects, dashboard)['error']['code'] == 'not_authorized'
    assert objects[0]['result'] == 2


def test_a_failing_receiver_leaves_the_call_standing_and_undoes_its_writes(mock_request) -> None:
    card = Glue.object(mock_request, CounterCardComponent(start=1))
    dashboard = Glue.object(mock_request, FailingDashboardComponent())

    objects = _call(mock_request, card, 'increment', [_receiver(dashboard)])

    assert objects[0]['result'] == 2
    assert _answer(objects, dashboard)['error']['code'] == 'glue_error'
    assert not Gorilla.objects.filter(name='Written by a failing receiver').exists()


def test_a_receiver_cannot_repeat_an_address_the_request_names(mock_request) -> None:
    card = Glue.object(mock_request, CounterCardComponent(start=1))
    entry = {
        'address': card.address,
        'policy_token': card.policy.token,
        'call': {'attribute': 'increment', 'kwargs': {}},
        'receivers': [{'address': card.address, 'policy_token': card.policy.token}],
    }
    request = RequestFactory().post('/__dg__/callable_attribute/', {'objects': json.dumps([entry])})
    request.session = mock_request.session

    response = GlueAttributeCallResolver.as_view()(request)

    assert response.status_code == 400
    assert json.loads(response.content)['result']['error']['code'] == 'duplicate_addresses'
