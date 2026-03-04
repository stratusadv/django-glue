from django.http import HttpRequest, HttpResponseRedirect
from django.shortcuts import render

from django_glue import Glue, GlueAccess
from test_project.gorilla.models import Gorilla


def flush_session_view(request: HttpRequest):
    """Flush the session and redirect back to the referring page."""
    request.session.flush()
    referer = request.META.get('HTTP_REFERER', '/')
    return HttpResponseRedirect(referer)


def stress_view(request: HttpRequest):
    """Stress test - load many glue objects."""
    Glue.queryset(
        request=request,
        target=Gorilla.objects.all(),
        unique_name='gorillas',
        access=GlueAccess.DELETE,
    )

    return render(
        request,
        'lab/performance/page/stress_page.html',
        context={
            'page_title': 'Test Lab',
            'page_heading': 'Stress Test',
            'page_subtitle': 'Load and interact with many Glue objects'

        }
    )
