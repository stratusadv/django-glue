from enum import StrEnum

from django.conf import settings
from django.http import HttpRequest, HttpResponseRedirect, HttpResponse
from django.shortcuts import render
from django.contrib import messages

from test_project.lab import benchmarks
from test_project.lab.models import Specimen

DEFAULT_COUNT = 100
DEFAULT_REPEATS = 5
DEFAULT_BATCH_SIZE = 25
DEFAULT_BATCHES = 120
DEFAULT_CARDS = 100
DEFAULT_DEPTH = 4
DEFAULT_FANOUT = 3


class Scenario(StrEnum):
    PAGE_LOAD = 'page_load'
    BATCH = 'batch'
    RELATED_BATCH = 'related_batch'
    SCROLL = 'scroll'
    COMPONENT_PAGE = 'component_page'
    COMPONENT_TREE = 'component_tree'
    COMPONENT_CALL = 'component_call'


def flush_session_view(request: HttpRequest) -> HttpResponse:
    """Flush the session and redirect back to the referring page."""
    request.session.flush()
    messages.error(request, 'Session has been flushed.')
    referer = request.META.get('HTTP_REFERER', '/')

    return HttpResponseRedirect(referer)


def stress_view(request: HttpRequest) -> HttpResponse:
    """Mounts many live components at once, for the metrics panel to watch."""
    cards = _bounded_int(request, 'cards', 50, maximum=500)
    tallies = _bounded_int(request, 'tallies', 5, maximum=100)
    depth = _bounded_int(request, 'depth', 3, maximum=5)
    fanout = _bounded_int(request, 'fanout', 3, maximum=4)

    context = {
        'page_title': 'Test Lab',
        'page_heading': 'Stress Test',
        'page_subtitle': 'Many live components at once; open the Glue panel and interact',
        'cards': cards,
        'tallies': tallies,
        'tally_keys': range(tallies),
        'depth': depth,
        'fanout': fanout,
    }

    return render(request, template_name='lab/performance/page/stress_page.html', context=context)


def speed_view(request: HttpRequest) -> HttpResponse:
    """Runs the one scenario named in the query string; the rest of the page only describes them."""
    count = _bounded_int(request, 'count', DEFAULT_COUNT, maximum=1000)
    repeats = _bounded_int(request, 'repeats', DEFAULT_REPEATS, maximum=20)
    batch_size = _bounded_int(request, 'batch_size', DEFAULT_BATCH_SIZE, maximum=500)
    batches = _bounded_int(request, 'batches', DEFAULT_BATCHES, maximum=500)
    cards = _bounded_int(request, 'cards', DEFAULT_CARDS, maximum=500)
    depth = _bounded_int(request, 'depth', DEFAULT_DEPTH, maximum=5)
    fanout = _bounded_int(request, 'fanout', DEFAULT_FANOUT, maximum=4)

    context = {
        'page_title': 'Test Lab',
        'page_heading': 'Speed Test',
        'page_subtitle': 'What Glue costs to put objects on a page and to answer a call',
        # Members by name: templates call a class, so the enum itself would render empty.
        'scenarios': Scenario.__members__,
        'debug': settings.DEBUG,
        'specimen_count': Specimen.objects.count(),
        'count': count,
        'repeats': repeats,
        'batch_size': batch_size,
        'batches': batches,
        'cards': cards,
        'depth': depth,
        'fanout': fanout,
    }

    scenario = request.GET.get('scenario')

    if scenario == Scenario.PAGE_LOAD:
        context['page_load'] = [
            (kind, benchmarks.measure_page_load(request, kind, count, repeats))
            for kind in benchmarks.PageObjectKind
        ]
    elif scenario == Scenario.BATCH:
        context['batch'] = benchmarks.measure_batch(request, batch_size, repeats)
    elif scenario == Scenario.RELATED_BATCH:
        context['related_batch'] = benchmarks.measure_batch(
            request,
            batch_size,
            repeats,
            related=True,
        )
    elif scenario == Scenario.SCROLL:
        context['scroll'] = benchmarks.measure_scroll(request, batch_size, batches)
    elif scenario == Scenario.COMPONENT_PAGE:
        context['component_page'] = benchmarks.measure_component_page(
            request,
            'lab/deck',
            repeats,
            size=cards,
        )
    elif scenario == Scenario.COMPONENT_TREE:
        # One row per depth, so the growth with nesting reads down the table.
        context['component_tree'] = [
            (
                sum(fanout ** step for step in range(level + 1)),
                benchmarks.measure_component_page(
                    request,
                    'lab/tree',
                    repeats,
                    depth=level,
                    fanout=fanout,
                ),
            )
            for level in range(1, depth + 1)
        ]
    elif scenario == Scenario.COMPONENT_CALL:
        context['component_call'] = [
            (call, benchmarks.measure_component_call(request, cards, call, repeats))
            for call in benchmarks.DeckCall
        ]

    return render(request, template_name='lab/performance/page/speed_page.html', context=context)


def _bounded_int(request: HttpRequest, name: str, default: int, *, maximum: int) -> int:
    try:
        value = int(request.GET.get(name, default))
    except ValueError:
        return default

    return min(max(value, 1), maximum)
