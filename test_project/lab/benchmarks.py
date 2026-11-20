"""
What Glue costs to put objects and components on a page and to answer a call,
measured in process against the lab's specimens and components, so the speed
page and the lab tests read the same numbers.
"""
from __future__ import annotations

import json
import re
import statistics
import time

from dataclasses import dataclass
from enum import StrEnum
from html import unescape
from typing import TYPE_CHECKING, Any

from django.db import connection
from django.template import engines
from django.test import RequestFactory
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils.html import json_script

from django_glue import Glue, GlueAccess
from django_glue.constants import DJANGO_GLUE_CONTEXT_KEY, DJANGO_GLUE_CONTEXT_SCRIPT_NAME
from django_glue.glue.context import GlueContextManager
from django_glue.resolver.attribute_call.resolver import GlueAttributeCallResolver
from test_project.lab.forms import SpecimenForm
from test_project.lab.models import Collector, Specimen

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from django.http import HttpRequest

SPECIMEN_FIELDS = ['id', 'name', 'species', 'weight', 'catalogue_number']
RELATED_SPECIMEN_FIELDS = [*SPECIMEN_FIELDS, 'collector', 'habitats']

CONTEXT_SCRIPT = re.compile(
    rf'<script id="{DJANGO_GLUE_CONTEXT_SCRIPT_NAME}" type="application/json">(.*?)</script>',
    re.DOTALL,
)
COMPONENT_OBJECTS = re.compile(r'data-glue-objects="([^"]*)"')


class PageObjectKind(StrEnum):
    MODEL = 'model'
    QUERYSET = 'queryset'
    FORM = 'form'


class DeckCall(StrEnum):
    """
    The deck's callables: a re-render that keeps its cards, one that spawns a
    card, one that drops one, and one that returns a new component.
    """

    TOUCH = 'touch'
    GROW = 'grow'
    SHRINK = 'shrink'
    OPEN_CARD = 'open_card'


@dataclass(frozen=True)
class Payload:
    """The bytes of an encoded response, and how many of them its entries' parts take."""

    total: int
    tokens: int
    static: int
    computed: int

    @classmethod
    def of(cls, entries: list[dict[str, Any]], total: int) -> Payload:
        return cls(
            total=total,
            tokens=sum(len(entry.get('policy_token', '')) for entry in entries),
            static=sum(len(json.dumps(entry.get('static_data', {}))) for entry in entries),
            computed=sum(len(json.dumps(entry.get('computed_data', {}))) for entry in entries),
        )


@dataclass(frozen=True)
class Measurement:
    milliseconds: float
    queries: int
    entries: int
    payload: Payload


@dataclass(frozen=True)
class ScrollStep:
    batch: int
    milliseconds: float
    token_bytes: int
    response_bytes: int
    error: str = ''


def measure_page_load(
    request: HttpRequest,
    kind: PageObjectKind,
    count: int,
    repeats: int,
) -> Measurement:
    """Registers ``count`` objects of one kind on a page and encodes them as the init tag does."""
    specimen = Specimen.objects.first()
    register: dict[PageObjectKind, Callable[[HttpRequest, str], Any]] = {
        PageObjectKind.MODEL: lambda page_request, name: Glue.model(
            request=page_request,
            unique_name=name,
            target=specimen,
            fields=RELATED_SPECIMEN_FIELDS,
        ),
        PageObjectKind.QUERYSET: lambda page_request, name: Glue.queryset(
            request=page_request,
            unique_name=name,
            target=Specimen.objects.all(),
            fields=SPECIMEN_FIELDS,
        ),
        PageObjectKind.FORM: lambda page_request, name: Glue.form(
            request=page_request,
            unique_name=name,
            target=SpecimenForm(),
        ),
    }

    def load_page() -> str:
        page_request = _page_request(request)
        for index in range(count):
            register[kind](page_request, f'{kind}_{index}')
        script = json_script(
            GlueContextManager(page_request).context_data[DJANGO_GLUE_CONTEXT_KEY],
            DJANGO_GLUE_CONTEXT_SCRIPT_NAME,
        )
        return script[script.index('>') + 1:script.rindex('<')]

    return _measure(load_page, repeats)


def measure_component_page(
    request: HttpRequest,
    tag_name: str,
    repeats: int,
    **parameters: int,
) -> Measurement:
    """
    Renders one component tag, children and all, plus the init script, as a
    page does; the entries counted are every copy sent, in stamped roots and in
    the init script alike.
    """
    template = _component_template(tag_name, **parameters)

    def load_page() -> str:
        page_request = _page_request(request)
        html = template.render({}, page_request)
        return html + json_script(
            GlueContextManager(page_request).context_data[DJANGO_GLUE_CONTEXT_KEY],
            DJANGO_GLUE_CONTEXT_SCRIPT_NAME,
        )

    return _measure(load_page, repeats, entries_of=lambda page: page_entries(page)[0])


def measure_component_call(
    request: HttpRequest,
    size: int,
    call: DeckCall,
    repeats: int,
) -> Measurement:
    """
    Calls one of a deck's callables with its ``size`` cards mounted, as the
    client sends it; the response carries the deck's re-render.
    """
    html = _component_template('lab/deck', size=size).render({}, _page_request(request))
    deck, *cards = page_entries(html)[0]

    return _measure(
        lambda: _call(request, deck, call, {}, mounted=[card['address'] for card in cards]),
        repeats,
    )


def measure_batch(
    request: HttpRequest,
    batch_size: int,
    repeats: int,
    *,
    related: bool = False,
) -> Measurement:
    """
    Answers one batch of specimens through the call endpoint; ``related`` adds
    each specimen's collector and habitats.
    """
    entry = _specimen_queryset_entry(request, batch_size, related=related)

    return _measure(lambda: _call(request, entry, 'query_with_params', {}), repeats)


def measure_scroll(request: HttpRequest, batch_size: int, batches: int) -> list[ScrollStep]:
    """Seeks batch after batch as infinite scroll does, carrying each successor token forward."""
    entry = _specimen_queryset_entry(request, batch_size, related=False)
    token = entry['policy_token']
    seek_key = None
    steps = []

    for batch in range(1, batches + 1):
        start = time.perf_counter()
        body = _call(
            request,
            {'address': entry['address'], 'policy_token': token},
            'query_with_params',
            {'seek_key': seek_key} if seek_key else {},
        )
        milliseconds = round((time.perf_counter() - start) * 1000, 1)
        answered = next(
            object_entry
            for object_entry in json.loads(body)['objects']
            if object_entry['address'] == entry['address']
        )
        error = answered.get('error', {}).get('code', '')
        steps.append(ScrollStep(batch, milliseconds, len(token), len(body), error))

        if error or not answered['result']['has_next']:
            break

        token = answered.get('policy_token', token)
        seek_key = answered['result']['seek_key']

    return steps


def page_entries(html: str) -> tuple[list[dict[str, Any]], int]:
    """
    Every entry a page carries, from its init script and from the roots its
    components stamped, with the bytes those take.
    """
    encoded = [match.group(1) for match in CONTEXT_SCRIPT.finditer(html)]
    encoded += [unescape(match.group(1)) for match in COMPONENT_OBJECTS.finditer(html)]

    entries = []
    for text in encoded:
        data = json.loads(text)
        entries += data['objects'] if isinstance(data, dict) else data

    return entries, sum(len(text) for text in encoded)


def _measure(
    run: Callable[[], str],
    repeats: int,
    entries_of: Callable[[str], list[dict[str, Any]]] = lambda body: json.loads(body)['objects'],
) -> Measurement:
    """
    Runs once to warm up, then ``repeats`` times; the time is the median, and
    the queries and bytes are the last run's.
    """
    run()
    timings = []
    for _ in range(repeats):
        with CaptureQueriesContext(connection) as queries:
            start = time.perf_counter()
            encoded = run()
            timings.append((time.perf_counter() - start) * 1000)

    entries = entries_of(encoded)
    return Measurement(
        milliseconds=round(statistics.median(timings), 1),
        queries=len(queries),
        entries=len(entries),
        payload=Payload.of(entries, len(encoded)),
    )


def _component_template(tag_name: str, **parameters: int) -> Any:
    arguments = ' '.join(f'{name}={value}' for name, value in parameters.items())
    return engines['django'].from_string(
        f"{{% load django_glue %}}{{% glue_component '{tag_name}' {arguments} %}}"
    )


def _page_request(request: HttpRequest) -> HttpRequest:
    """A speed page request sharing the viewer's session and user, so its tokens verify."""
    page_request = RequestFactory().get(reverse('lab:performance:speed'))
    page_request.session = request.session
    page_request.user = request.user
    return page_request


def _specimen_queryset_entry(
    request: HttpRequest,
    batch_size: int,
    *,
    related: bool,
) -> dict[str, Any]:
    page_request = _page_request(request)
    Glue.queryset(
        request=page_request,
        unique_name='specimens',
        target=Specimen.objects.all(),
        access=GlueAccess.VIEW,
        fields=RELATED_SPECIMEN_FIELDS if related else SPECIMEN_FIELDS,
        choices=(
            {'collector': Glue.choices(Collector.objects.all(), search_fields=['name'])}
            if related
            else None
        ),
        batch_size=batch_size,
    )
    return GlueContextManager(page_request).serialized_objects[0]


def _call(
    request: HttpRequest,
    entry: dict[str, Any],
    attribute: str,
    kwargs: dict[str, Any],
    mounted: Sequence[str] = (),
) -> str:
    """Posts one entry's call to the call endpoint, as the client does; returns the body."""
    requested = {
        'address': entry['address'],
        'policy_token': entry['policy_token'],
        'call': {'attribute': attribute, 'kwargs': kwargs},
    }
    if mounted:
        requested['mounted'] = list(mounted)

    call_request = RequestFactory().post(
        reverse('__dg__:callable_attribute'),
        {'objects': json.dumps([requested])},
    )
    call_request.session = request.session
    call_request.user = request.user
    return GlueAttributeCallResolver.as_view()(call_request).content.decode()
