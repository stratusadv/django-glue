"""
Glue metrics on every test project page, while DEBUG is on. Each response
reports its server time, queries and Glue payload in a ``Server-Timing``
header, which the browser hands to page scripts for navigations and fetches
alike; HTML pages get the panel that shows those beside the browser's own
timings.
"""
from __future__ import annotations

import json
import re
import time

from collections import Counter
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.core.exceptions import MiddlewareNotUsed
from django.db import connection
from django.template.loader import render_to_string
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from test_project.lab.benchmarks import Payload, page_entries

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.http import HttpRequest, HttpResponse

HEAD_OPEN = re.compile(r'<head[^>]*>', re.IGNORECASE)
CHILD_SEGMENT = re.compile(r'\[([^\[\]]*)\]')
ROOT_HASH = re.compile(r'_[0-9a-f]{16}$')


class Metric(StrEnum):
    SERVER = 'server'
    QUERIES = 'queries'
    ENTRIES = 'glue-entries'
    BYTES = 'glue-bytes'
    TOKENS = 'glue-tokens'
    STATIC = 'glue-static'
    COMPUTED = 'glue-computed'
    CALLS = 'glue-calls'
    ERRORS = 'glue-errors'


class GlueMetricsMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        if not settings.DEBUG:
            raise MiddlewareNotUsed
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        with CaptureQueriesContext(connection) as queries:
            start = time.perf_counter()
            response = self.get_response(request)
            milliseconds = (time.perf_counter() - start) * 1000

        if getattr(response, 'streaming', False):
            return response

        timings = [
            _server_timing(Metric.SERVER, round(milliseconds, 1)),
            _server_timing(Metric.QUERIES, len(queries)),
        ]
        content_type = response.get('Content-Type', '')

        if 'json' in content_type:
            timings += _json_timings(request, response)
        elif 'text/html' in content_type:
            timings += _payload_timings(*page_entries(response.content.decode()))
            _inject_panel(response)

        response['Server-Timing'] = ', '.join(timings)
        return response


def _json_timings(request: HttpRequest, response: HttpResponse) -> list[str]:
    """A Glue call or view reply: its entries' payload, what was called and what failed."""
    try:
        objects = json.loads(response.content).get('objects')
    except (ValueError, AttributeError):
        return []
    if not isinstance(objects, list):
        return []

    timings = _payload_timings(objects, len(response.content))

    if request.path == reverse('__dg__:callable_attribute'):
        # One batch can wake many components; repeats read as "name.attribute xN",
        # kept to ASCII because it travels in a header.
        calls = Counter(
            f'{_address_label(entry["address"])}.{entry["call"]["attribute"]}'
            for entry in json.loads(request.POST.get('objects', '[]'))
            if entry.get('call')
        )
        description = ', '.join(
            label if count == 1 else f'{label} x{count}' for label, count in calls.items()
        )
        timings.append(_server_timing(Metric.CALLS, description=description or 'refresh'))

    errors = [entry['error']['code'] for entry in objects if 'error' in entry]
    if errors:
        timings.append(_server_timing(Metric.ERRORS, description=', '.join(errors)))

    return timings


def _address_label(address: str) -> str:
    """
    A readable name for an address: the innermost child segment without its
    fingerprint (``lab/card:int:3`` from ``deck#token[lab/card:int:3:61d5]``),
    or a root's name without the hash that tells same-tag roots apart.
    """
    segments = CHILD_SEGMENT.findall(address)
    if segments:
        return segments[-1].rsplit(':', 1)[0]
    return ROOT_HASH.sub('', address.split('#', 1)[0])


def _payload_timings(objects: list[dict[str, Any]], total: int) -> list[str]:
    payload = Payload.of(objects, total)
    return [
        _server_timing(Metric.ENTRIES, len(objects)),
        _server_timing(Metric.BYTES, payload.total),
        _server_timing(Metric.TOKENS, payload.tokens),
        _server_timing(Metric.STATIC, payload.static),
        _server_timing(Metric.COMPUTED, payload.computed),
    ]


def _server_timing(name: Metric, value: float | None = None, description: str = '') -> str:
    """One ``Server-Timing`` metric; counts and bytes ride in ``dur``, the one numeric field."""
    parts = [str(name)]
    if value is not None:
        parts.append(f'dur={value}')
    if description:
        escaped = description.replace('\\', '\\\\').replace('"', '\\"')
        parts.append(f'desc="{escaped}"')
    return ';'.join(parts)


def _inject_panel(response: HttpResponse) -> None:
    """
    The panel's script goes first in the head, so it wraps ``fetch`` before any
    page script can call it; it builds its markup once the body exists.
    """
    html = response.content.decode()
    head = HEAD_OPEN.search(html)
    if head is None:
        return

    panel = render_to_string('lab/metrics/panel.html', {'metrics': dict(Metric.__members__)})
    response.content = html[:head.end()] + panel + html[head.end():]
    if response.has_header('Content-Length'):
        response['Content-Length'] = str(len(response.content))
