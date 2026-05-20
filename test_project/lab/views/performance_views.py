import time
from typing import Any
from uuid import uuid4

from django.http import HttpRequest, HttpResponseRedirect, HttpResponse
from django.shortcuts import render

from django_glue import Glue
from django_glue.proxies import GlueModelProxy, GlueQuerySetProxy, GlueFormProxy
from test_project.gorilla.forms import GorillaForm
from test_project.gorilla.models import Gorilla


def flush_session_view(request: HttpRequest) -> HttpResponse:
    """Flush the session and redirect back to the referring page."""
    request.session.flush()
    referer = request.META.get('HTTP_REFERER', '/')

    return HttpResponseRedirect(referer)


def stress_view(request: HttpRequest) -> HttpResponse:
    context = {
        'page_title': 'Test Lab',
        'page_heading': 'Stress Test',
        'page_subtitle': 'Load and interact with many Glue objects',
    }


    return render(request, template_name='lab/performance/page/stress_page.html', context=context)


def speed_view(request: HttpRequest) -> HttpResponse:
    counts = (1, 10, 100, 1000)

    unique_names = [str(uuid4()) for _ in range(max(counts))]

    glue_types_targets = {
        'model': (Gorilla.objects.first(), GlueModelProxy),
        'querySet': (Gorilla.objects.all(), GlueQuerySetProxy),
        'form': (GorillaForm(), GlueFormProxy),
    }

    context = {
        'page_title': 'Test Lab',
        'page_heading': 'Speed Test',
        'page_subtitle': 'Load and Measure Speed with many Glue objects in Seconds',
        'glue_types_results': {glue_type: {} for glue_type in glue_types_targets},
        'unique_names': unique_names,
        'counts': counts,
    }

    def glue_amount(count: int, target: Any, proxy_class: Any) -> None:
        for unique_name in unique_names[:count]:
            Glue.glue(
                request=request, target=target, proxy_class=proxy_class, unique_name=unique_name
            )

    for glue_type, target in glue_types_targets.items():
        for count in counts:
            start_time = time.time()
            glue_amount(count, target[0], target[1])
            context['glue_types_results'][glue_type][count] = f'{(time.time() - start_time):.4f}'

    return render(request, template_name='lab/performance/page/speed_page.html', context=context)
