"""Morph lab.

Proves out what survives when server-rendered HTML is re-applied to a live DOM
region, under three strategies: naive replacement (what django-glue does today),
idiomorph (framework-agnostic), and Alpine's own morph plugin.

The region is shaped like a component tree: one root element containing cards
that each carry a stable id (the address analogue), local Alpine state, a
focusable input, and -- on one card -- a node whose content is owned by
imperative third-party JS rather than by the server render.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from django.shortcuts import render

if TYPE_CHECKING:
    from django.http import HttpRequest, HttpResponse

CARD_KEYS = ('alpha', 'bravo', 'charlie', 'delta')


def _cards(order: str, count: int, version: int) -> list[dict]:
    keys = list(CARD_KEYS)[:count]

    if order == 'reversed':
        keys.reverse()

    return [
        {
            'key': key,
            'label': key.title(),
            'server_value': f'{key}-v{version}',
            # Only one card stands in for third-party-owned DOM (a chart, a date
            # picker) whose children are written by JS after mount and are not
            # represented in the server render at all.
            'third_party': key == 'charlie',
        }
        for key in keys
    ]


def morph_view(request: HttpRequest) -> HttpResponse:
    context = {
        'page_title': 'Test Lab',
        'page_heading': 'Morph Lab',
        'page_subtitle': 'What survives when server HTML is re-applied to a live region',
        'cards': _cards('normal', len(CARD_KEYS), 1),
    }

    return render(request, template_name='lab/morph/page/morph_page.html', context=context)


def morph_region_view(request: HttpRequest) -> HttpResponse:
    """Return just the region markup, with the requested shape."""
    order = request.GET.get('order', 'normal')
    count = int(request.GET.get('count', len(CARD_KEYS)))
    version = int(request.GET.get('version', 2))

    return render(
        request,
        template_name='lab/morph/region.html',
        context={'cards': _cards(order, count, version)},
    )
