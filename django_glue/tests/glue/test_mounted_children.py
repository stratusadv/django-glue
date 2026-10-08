"""A parent's re-render keeps the children the client reports mounted (ADR 025)."""

from __future__ import annotations

import json
from typing import Any

import pytest
from django.template import Context, Template, TemplateSyntaxError
from django.test import RequestFactory

from django_glue import Glue
from django_glue.exceptions import GlueComponentKeyError, GlueComponentParameterError
from django_glue.glue.components.component import MOUNTED_CHILDREN_CONTEXT_KEY
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


def _stamp(request, source: str, mounted: frozenset[str] = frozenset(), **context: Any) -> str:
    parent = Glue.object(request, WeekColumnsComponent())
    return Template('{% load django_glue %}' + source).render(Context({
        'request': request,
        'component': parent,
        MOUNTED_CHILDREN_CONTEXT_KEY: mounted,
        **context,
    }))


def _card_addresses(request) -> list[str]:
    return [
        entry['address']
        for entry in GlueContextManager(request).serialized_objects
        if GluePolicy.from_token(entry['policy_token']).identity.get('component_id', '').endswith(
            '.CounterCardComponent'
        )
    ]


def _later_request(request):
    """A later request in the same session, as the client's next call is."""
    later = RequestFactory().post('/__dg__/callable_attribute/')
    later.session = request.session
    return later


def _call(request, component, attribute: str, mounted: list[str]) -> dict[str, Any]:
    context = AttributeCallBatchContext.model_construct(
        request=_later_request(request),
        entries=[AddressedObjectEntry(
            address=component.address,
            policy_token=component.policy.token,
            call=AttributeCall(attribute=attribute),
            mounted=mounted,
        )],
    )
    response = GlueAttributeCallResolver()._resolve_json_response_from_context(context)
    return json.loads(response.content)['objects'][0]


CARD = "{% glue_component 'gorilla/counter_card' start=start key='card' %}"


def test_a_stamped_childs_address_changes_with_its_parameters(mock_request) -> None:
    _stamp(mock_request, CARD, start=1)
    [first] = _card_addresses(mock_request)
    later = _later_request(mock_request)

    _stamp(later, CARD, start=2)
    [second] = _card_addresses(later)

    assert first != second


GREETING_CARD = (
    "{% glue_component 'gorilla/greeting_counter_card' start=1 visitor=visitor key='card' %}"
)


def _root_address(html: str) -> str:
    return html.split('data-glue-address="', 1)[1].split('"', 1)[0]


def test_a_stamped_childs_address_changes_with_a_value_passed_to_post_init(mock_request) -> None:
    first = _root_address(_stamp(mock_request, GREETING_CARD, visitor='Koko'))
    same = _root_address(_stamp(_later_request(mock_request), GREETING_CARD, visitor='Koko'))
    changed = _root_address(_stamp(_later_request(mock_request), GREETING_CARD, visitor='Harambe'))

    assert first == same
    assert first != changed


def test_a_value_stamped_for_post_init_must_be_serializable(mock_request) -> None:
    with pytest.raises(GlueComponentParameterError, match='JSON-serializable'):
        _stamp(mock_request, GREETING_CARD, visitor=object())


def test_a_mounted_child_renders_a_placeholder_and_is_not_introduced(mock_request) -> None:
    _stamp(mock_request, CARD, start=1)
    [address] = _card_addresses(mock_request)
    later = _later_request(mock_request)

    html = _stamp(later, CARD, mounted=frozenset([address]), start=1)

    assert html == f'<template data-glue-keep="{address}"></template>'
    assert _card_addresses(later) == []


def test_a_child_stamped_with_new_parameters_renders_although_its_old_address_is_mounted(mock_request) -> None:
    _stamp(mock_request, CARD, start=1)
    [address] = _card_addresses(mock_request)
    later = _later_request(mock_request)

    html = _stamp(later, CARD, mounted=frozenset([address]), start=2)

    assert 'data-testid="counter-card"' in html
    assert _card_addresses(later) != [address]


def test_rerender_with_parent_renders_a_mounted_child(mock_request) -> None:
    flagged = "{% glue_component 'gorilla/counter_card' start=1 key='card' rerender_with_parent %}"
    _stamp(mock_request, flagged)
    [address] = _card_addresses(mock_request)
    later = _later_request(mock_request)

    html = _stamp(later, flagged, mounted=frozenset([address]))

    assert 'data-testid="counter-card"' in html
    assert _card_addresses(later) == [address]


def test_two_kept_children_with_one_key_are_still_rejected(mock_request) -> None:
    _stamp(mock_request, CARD, start=1)
    [address] = _card_addresses(mock_request)
    later = _later_request(mock_request)

    with pytest.raises(GlueComponentKeyError, match='share key'):
        _stamp(later, CARD + CARD, mounted=frozenset([address]), start=1)


def test_an_unknown_bare_word_is_a_template_syntax_error() -> None:
    with pytest.raises(TemplateSyntaxError, match='rerender_with_parent flag'):
        Template("{% load django_glue %}{% glue_component 'gorilla/counter_card' start=1 rerender_with_parnet %}")


def test_a_components_rerender_keeps_the_children_its_entry_lists(mock_request) -> None:
    dashboard = Glue.object(mock_request, CounterDashboardComponent())
    dashboard.render()
    cards = _card_addresses(mock_request)

    entry = _call(mock_request, dashboard, 'drop_first', mounted=cards)

    kept = [card for card in cards if f'data-glue-keep="{card}"' in entry['html']]
    assert len(kept) == 1
    assert 'data-testid="counter-card"' not in entry['html']


def test_a_direct_render_call_renders_every_child(mock_request) -> None:
    """Its HTML may be placed anywhere, where no live child can stand in."""
    dashboard = Glue.object(mock_request, CounterDashboardComponent())
    dashboard.render()
    cards = _card_addresses(mock_request)

    entry = _call(mock_request, dashboard, 'render', mounted=cards)

    assert 'data-glue-keep' not in entry['html']
    assert entry['html'].count('data-testid="counter-card"') == 2
