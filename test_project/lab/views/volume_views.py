from django.contrib import messages
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_POST

from django_glue import Glue, GlueAccess
from test_project.lab.models import SPECIES, Specimen

DEFAULT_SEED_COUNT = 100_000
BATCH_SIZE = 25


def volume_view(request: HttpRequest) -> HttpResponse:
    Glue.queryset(
        request=request,
        unique_name='specimens',
        target=Specimen.objects.all(),
        access=GlueAccess.VIEW,
        fields=['id', 'name', 'species', 'weight', 'catalogue_number'],
        batch_size=BATCH_SIZE,
    )

    context = {
        'page_title': 'Test Lab',
        'page_heading': 'Volume Test',
        'page_subtitle': 'Search and seek through a queryset of 100,000 rows without loading it into the browser',
        'specimen_count': Specimen.objects.count(),
        'default_seed_count': DEFAULT_SEED_COUNT,
        'batch_size': BATCH_SIZE,
        'species_choices': SPECIES,
    }

    return render(request, template_name='lab/performance/page/volume_page.html', context=context)


@require_POST
def seed_specimens_view(request: HttpRequest) -> HttpResponse:
    count = int(request.POST.get('count', DEFAULT_SEED_COUNT))
    created = Specimen.seed(count)
    messages.success(request, f'Seeded {created:,} specimens.')

    return HttpResponseRedirect(reverse('lab:performance:volume'))


@require_POST
def clear_specimens_view(request: HttpRequest) -> HttpResponse:
    deleted, _ = Specimen.objects.all().delete()
    messages.error(request, f'Deleted {deleted:,} specimens.')

    return HttpResponseRedirect(reverse('lab:performance:volume'))
