"""A parent's re-render keeps the children the client reports mounted (ADR 025)."""

from __future__ import annotations

import json
from typing import Any

import pytest
from django.template import Context, Template, TemplateSyntaxError
from django.test import RequestFactory

from django_glue import Glue
from django_glue.glue.component_tag import MOUNTED_ADDRESSES_ATTR
from django_glue.glue.context import GlueContextManager
from django_glue.glue.policy import GluePolicy
from django_glue.resolver.attribute_call.context import (
    AddressedObjectEntry,
    AttributeCall,
    AttributeCallBatchContext,
)
from django_glue.resolver.attribute_call.resolver import GlueAttributeCallResolver
from test_project.gorilla.components import CounterDashboardComponent


class WeekColumnsComponent(Glue.Component):
    template = 'glue_template_test.html'


def _stamp(request, source: str, **context: Any) -> str:
    parent = Glue.object(request, WeekColumnsComponent())
    return Template('{% load django_glue %}' + source).render(
        Context({'request': request, 'component': parent, **context})
    )


def _card_addresses(request) -> list[str]:
    return [
        entry['address']
        for entry in GlueContextManager(request).serialized_objects
        if GluePolicy.from_token(entry['policy_token']).identity.get('component_id', '').endswith(
            '.CounterCardComponent'
        )
    ]


def _later_request(request, mounted: list[str]):
    later = RequestFactory().post('/__dg__/callable_attribute/')
    later.session = request.session
    later.__dict__[MOUNTED_ADDRESSES_ATTR] = frozenset(mounted)
    return later


CARD = "{% glue_component 'gorilla/counter_card' start=start key='card' %}"


def test_a_stamped_childs_address_changes_with_its_parameters(mock_request) -> None:
    _stamp(mock_request, CARD, start=1)
    [first] = _card_addresses(mock_request)
    request = RequestFactory().get('/')
    request.session = mock_request.session

    _stamp(request, CARD, start=2)
    [second] = _card_addresses(request)

    assert first != second


def test_a_mounted_child_renders_a_placeholder_and_is_not_introduced(mock_request) -> None:
    _stamp(mock_request, CARD, start=1)
    [address] = _card_addresses(mock_request)
    later = _later_request(mock_request, [address])

    html = _stamp(later, CARD, start=1)

    assert html == f'<template data-glue-keep="{address}"></template>'
    assert _card_addresses(later) == []


def test_a_child_stamped_with_new_parameters_renders_although_its_old_address_is_mounted(mock_request) -> None:
    _stamp(mock_request, CARD, start=1)
    [address] = _card_addresses(mock_request)
    later = _later_request(mock_request, [address])

    html = _stamp(later, CARD, start=2)

    assert 'data-testid="counter-card"' in html
    assert _card_addresses(later) != [address]


def test_rerender_with_parent_renders_a_mounted_child(mock_request) -> None:
    flagged = "{% glue_component 'gorilla/counter_card' start=1 key='card' rerender_with_parent %}"
    _stamp(mock_request, flagged)
    [address] = _card_addresses(mock_request)
    later = _later_request(mock_request, [address])

    html = _stamp(later, flagged)

    assert 'data-testid="counter-card"' in html
    assert _card_addresses(later) == [address]


def test_an_unknown_bare_word_is_a_template_syntax_error() -> None:
    with pytest.raises(TemplateSyntaxError, match='rerender_with_parent flag'):
        Template("{% load django_glue %}{% glue_component 'gorilla/counter_card' start=1 rerender_with_parnet %}")


def test_a_parent_call_keeps_the_children_its_request_lists(mock_request) -> None:
    dashboard = Glue.object(mock_request, CounterDashboardComponent())
    dashboard.render()
    cards = _card_addresses(mock_request)
    later = _later_request(mock_request, [])
    context = AttributeCallBatchContext.model_construct(
        request=later,
        entries=[AddressedObjectEntry(
            address=dashboard.address,
            policy_token=dashboard.policy.token,
            call=AttributeCall(attribute='drop_first'),
            mounted=cards,
        )],
    )

    response = GlueAttributeCallResolver()._resolve_json_response_from_context(context)

    [entry] = json.loads(response.content)['objects']
    kept = [card for card in cards if f'data-glue-keep="{card}"' in entry['html']]
    assert len(kept) == 1
    assert 'data-testid="counter-card"' not in entry['html']
