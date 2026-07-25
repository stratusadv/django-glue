import time
from uuid import uuid4

from django.http import HttpRequest, HttpResponseRedirect, HttpResponse
from django.shortcuts import render
from django.contrib import messages

from django_glue import Glue
from test_project.gorilla.forms import GorillaForm
from test_project.gorilla.models import Gorilla


def flush_session_view(request: HttpRequest) -> HttpResponse:
    """Flush the session and redirect back to the referring page."""
    request.session.flush()
    messages.error(request, 'Session has been flushed.')
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

    glue_types = ('model', 'querySet', 'form')

    context = {
        'page_title': 'Test Lab',
        'page_heading': 'Speed Test',
        'page_subtitle': 'Load and Measure Speed with many Glue objects in Seconds',
        'glue_types_results': {glue_type: {} for glue_type in glue_types},
        'unique_names': unique_names,
        'counts': counts,
    }

    def glue_amount(glue_type: str, count: int) -> None:
        for unique_name in unique_names[:count]:
            if glue_type == 'model':
                Glue.model(
                    request=request,
                    target=Gorilla.objects.first(),
                    unique_name=unique_name,
                    exclude=['signature'],
                )
            elif glue_type == 'querySet':
                Glue.queryset(
                    request=request,
                    target=Gorilla.objects.all(),
                    unique_name=unique_name,
                    exclude=['signature'],
                )
            elif glue_type == 'form':
                Glue.form(request=request, target=GorillaForm(), unique_name=unique_name)

    for glue_type in glue_types:
        for count in counts:
            start_time = time.time()
            glue_amount(glue_type, count)
            context['glue_types_results'][glue_type][count] = f'{(time.time() - start_time):.4f}'

    return render(request, template_name='lab/performance/page/speed_page.html', context=context)
