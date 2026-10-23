from __future__ import annotations

import json
import re
from html import unescape
from typing import TYPE_CHECKING, Any, ClassVar
from unittest.mock import patch

import pytest
from django.conf import settings
from django.core import signing
from django.core.exceptions import MiddlewareNotUsed, PermissionDenied
from django.http import Http404
from django.test import override_settings
from django.urls import resolve, reverse

from django_glue.glue.operation import GlueOperationKind
from django_glue.glue.policy import GluePolicy, GluePolicyTokenSerializer
from django_glue.middleware import GlueCall, GlueMiddlewareMixin
from django_glue.middleware.call import glue_call_hooks
from test_project.gorilla.components import CounterCardComponent

if TYPE_CHECKING:
    from collections.abc import Iterator

    from django.http import HttpRequest, HttpResponse
    from django.test import Client


pytestmark = pytest.mark.django_db

MODULE = 'django_glue.tests.test_call_middleware'

Guard = type['RouteGuardMiddleware']


class RouteGuardMiddleware(GlueMiddlewareMixin):
    """Denies Glue calls on objects issued under a denied route."""

    seen: ClassVar[list[GlueCall]] = []
    denied_routes: ClassVar[set[str]] = set()
    denial: ClassVar[type[Exception]] = PermissionDenied

    def __init__(self, get_response: Any) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> Any:
        return self.get_response(request)

    def process_glue_call(self, request: HttpRequest, glue_call: GlueCall) -> None:
        _ = request
        type(self).seen.append(glue_call)
        if glue_call.origin.url_name in self.denied_routes:
            raise self.denial


class DuckTypedHookMiddleware:
    """Defines the hook without the mixin, as Django finds ``process_view``."""

    def __init__(self, get_response: Any) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> Any:
        return self.get_response(request)

    def process_glue_call(self, request: HttpRequest, glue_call: GlueCall) -> None:
        _ = request, glue_call


class MixinOnlyMiddleware(GlueMiddlewareMixin):
    """Inherits the mixin's no-op hook, so it guards nothing."""

    def __init__(self, get_response: Any) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> Any:
        return self.get_response(request)


class UnusedHookMiddleware(GlueMiddlewareMixin):
    """Opts out at startup, as Django lets any middleware do."""

    def __init__(self, get_response: Any) -> None:
        _ = get_response
        raise MiddlewareNotUsed

    def process_glue_call(self, request: HttpRequest, glue_call: GlueCall) -> None:
        _ = request, glue_call
        raise PermissionDenied


def _middleware_with(*paths: str) -> list[str]:
    """The test project's middleware with ``paths`` before the Glue view middleware."""
    *leading, glue_view = settings.MIDDLEWARE
    return [*leading, *paths, glue_view]


@pytest.fixture
def route_guard() -> Iterator[type[RouteGuardMiddleware]]:
    RouteGuardMiddleware.seen = []
    RouteGuardMiddleware.denied_routes = set()
    RouteGuardMiddleware.denial = PermissionDenied
    with override_settings(MIDDLEWARE=_middleware_with(f'{MODULE}.RouteGuardMiddleware')):
        yield RouteGuardMiddleware


def _entries(response: HttpResponse) -> list[dict[str, Any]]:
    html = response.content.decode()
    entries = []
    for match in re.finditer(r'data-glue-objects="([^"]+)"', html):
        entries.extend(json.loads(unescape(match.group(1))))
    return entries


def _card_entry(client: Client, start: int) -> dict[str, Any]:
    response = client.get(reverse('gorilla:component_card_fragment', kwargs={'start': start}))
    return _entries(response)[0]


def _call(client: Client, *requested: dict[str, Any]) -> dict[str, dict[str, Any]]:
    response = client.post(
        reverse('__dg__:callable_attribute'),
        {'objects': json.dumps(list(requested))},
    )
    assert response.status_code == 200
    return {entry['address']: entry for entry in response.json()['objects']}


def _refresh(entry: dict[str, Any]) -> dict[str, Any]:
    return {'address': entry['address'], 'policy_token': entry['policy_token']}


def _increment(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        'address': entry['address'],
        'policy_token': entry['policy_token'],
        'call': {'attribute': 'increment', 'kwargs': {}},
    }


def _resigned(token: str, **changes: Any) -> str:
    """The token's payload with ``changes`` applied (``None`` removes a field), signed again."""
    payload = signing.loads(token, salt=GluePolicy.TOKEN_SALT, serializer=GluePolicyTokenSerializer)
    for field, value in changes.items():
        if value is None:
            payload.pop(field)
        else:
            payload[field] = value
    return signing.dumps(
        payload,
        salt=GluePolicy.TOKEN_SALT,
        serializer=GluePolicyTokenSerializer,
        compress=False,
    )


def test_a_policy_signs_the_path_that_issued_it(client: Client) -> None:
    entry = _card_entry(client, 7)

    assert GluePolicy.from_token(entry['policy_token']).origin == '/components/card/7/'


def test_a_stamped_child_signs_its_page_path(client: Client) -> None:
    response = client.get(reverse('gorilla:component_tally'))

    origins = {GluePolicy.from_token(entry['policy_token']).origin for entry in _entries(response)}

    assert origins == {'/components/tally/'}


def test_a_successor_token_keeps_the_origin_not_the_call_endpoint(client: Client) -> None:
    entry = _card_entry(client, 7)

    result = _call(client, _increment(entry))[entry['address']]

    assert GluePolicy.from_token(result['policy_token']).origin == '/components/card/7/'


def test_the_hook_sees_the_resolved_origin_and_the_call(client: Client, route_guard: Guard) -> None:
    entry = _card_entry(client, 7)

    result = _call(client, _increment(entry))[entry['address']]

    assert 'error' not in result
    [glue_call] = route_guard.seen
    assert glue_call.origin.url_name == 'component_card_fragment'
    assert glue_call.origin.kwargs == {'start': 7}
    assert glue_call.address == entry['address']
    assert glue_call.namespace == GluePolicy.from_token(entry['policy_token']).namespace
    assert glue_call.kind is GlueOperationKind.CALL
    assert glue_call.attribute == 'increment'


def test_a_refresh_is_seen_as_a_refresh(client: Client, route_guard: Guard) -> None:
    entry = _card_entry(client, 7)

    _call(client, _refresh(entry))

    [glue_call] = route_guard.seen
    assert glue_call.kind is GlueOperationKind.REFRESH
    assert glue_call.attribute is None


@pytest.mark.parametrize('denial', [PermissionDenied, Http404])
def test_a_denial_refuses_only_its_own_entry(
    client: Client,
    route_guard: Guard,
    denial: type[Exception],
) -> None:
    route_guard.denial = denial
    route_guard.denied_routes = {'component_card_fragment'}
    allowed = _entries(client.get(reverse('gorilla:component_tally')))[0]
    denied = _card_entry(client, 7)

    results = _call(client, _refresh(allowed), _increment(denied))

    assert 'error' not in results[allowed['address']]
    error = results[denied['address']]['error']
    assert error['code'] == 'not_authorized'
    assert error['details']['kind'] == 'call'
    assert error['details']['attribute'] == 'increment'


def test_a_denied_object_is_never_rebuilt(client: Client, route_guard: Guard) -> None:
    route_guard.denied_routes = {'component_card_fragment'}
    entry = _card_entry(client, 7)

    with patch.object(CounterCardComponent, '_reconstruct_from_policy') as reconstruct:
        result = _call(client, _increment(entry))[entry['address']]

    assert result['error']['code'] == 'not_authorized'
    reconstruct.assert_not_called()


def test_an_origin_that_no_longer_resolves_is_refused_when_a_hook_is_installed(
    client: Client,
    route_guard: Guard,
) -> None:
    entry = _card_entry(client, 7)
    moved = {**entry, 'policy_token': _resigned(entry['policy_token'], origin='/no/such/route/')}

    result = _call(client, _increment(moved))[entry['address']]

    assert result['error']['code'] == 'not_authorized'
    assert route_guard.seen == []


def test_an_origin_is_never_resolved_without_a_hook(client: Client) -> None:
    entry = _card_entry(client, 7)
    moved = {**entry, 'policy_token': _resigned(entry['policy_token'], origin='/no/such/route/')}

    result = _call(client, _increment(moved))[entry['address']]

    assert 'error' not in result
    assert result['result'] == 8


def test_a_token_without_an_origin_is_refused(client: Client) -> None:
    entry = _card_entry(client, 7)
    stale = {**entry, 'policy_token': _resigned(entry['policy_token'], origin=None)}

    result = _call(client, _increment(stale))[entry['address']]

    assert result['error']['code'] == 'proxy_policy_invalid'


def test_an_origin_shared_by_a_batch_is_resolved_once(client: Client, route_guard: Guard) -> None:
    page = client.get(reverse('gorilla:component_tally'))
    requested = [_refresh(entry) for entry in _entries(page)]
    assert len(requested) > 1

    with patch('django_glue.middleware.call.resolve', wraps=resolve) as resolver:
        _call(client, *requested)

    assert len(route_guard.seen) == len(requested)
    resolver.assert_called_once_with('/components/tally/')


def test_hooks_are_found_in_middleware_order() -> None:
    paths = [
        f'{MODULE}.MixinOnlyMiddleware',
        f'{MODULE}.DuckTypedHookMiddleware',
        f'{MODULE}.UnusedHookMiddleware',
        f'{MODULE}.RouteGuardMiddleware',
    ]
    with override_settings(MIDDLEWARE=_middleware_with(*paths)):
        hooks = glue_call_hooks()

    hook_classes = [type(hook.__self__) for hook in hooks]
    assert hook_classes == [DuckTypedHookMiddleware, RouteGuardMiddleware]


def test_hook_discovery_follows_a_middleware_change() -> None:
    with override_settings(MIDDLEWARE=_middleware_with(f'{MODULE}.RouteGuardMiddleware')):
        assert len(glue_call_hooks()) == 1

    assert glue_call_hooks() == ()
