from __future__ import annotations

import json
from typing import Any

import pytest
from django.test import RequestFactory, override_settings

from django_glue.exceptions import GlueRequestError, GlueRequestErrorCode
from django_glue.resolver.attribute_call.context import AttributeCallContextFactory


def entry(address: str, receivers: tuple[str, ...] = ()) -> dict[str, Any]:
    return {
        'address': address,
        'policy_token': 'token',
        'call': {'attribute': 'save'},
        'receivers': [{'address': receiver, 'policy_token': 'token'} for receiver in receivers],
    }


def parse(body: str) -> list[Any]:
    request = RequestFactory().post('/__dg__/callable_attribute/', data={'objects': body})
    return AttributeCallContextFactory(request).create().entries


@override_settings(DJANGO_GLUE_MAX_REQUEST_ADDRESSES=3)
def test_a_request_at_the_address_limit_is_parsed() -> None:
    entries = parse(json.dumps([entry('a'), entry('b'), entry('c')]))

    assert [item.address for item in entries] == ['a', 'b', 'c']


@override_settings(DJANGO_GLUE_MAX_REQUEST_ADDRESSES=3)
def test_a_request_over_the_address_limit_is_refused() -> None:
    with pytest.raises(GlueRequestError) as error:
        parse(json.dumps([entry('a'), entry('b'), entry('c'), entry('d')]))

    assert error.value.code == GlueRequestErrorCode.TOO_MANY_ADDRESSES


@override_settings(DJANGO_GLUE_MAX_REQUEST_ADDRESSES=3)
def test_receivers_count_toward_the_address_limit() -> None:
    with pytest.raises(GlueRequestError) as error:
        parse(json.dumps([entry('a', receivers=('b', 'c')), entry('d')]))

    assert error.value.code == GlueRequestErrorCode.TOO_MANY_ADDRESSES


def test_deeply_nested_json_is_invalid_json() -> None:
    with pytest.raises(GlueRequestError) as error:
        parse('[' * 200_000 + ']' * 200_000)

    assert error.value.code == GlueRequestErrorCode.INVALID_JSON
