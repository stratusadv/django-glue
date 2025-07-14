from django.template.response import TemplateResponse

import django_glue as dg

from test_project.app.glue_model_object import models
from test_project.app.glue_model_object.models import TestGlueModelObject


def dashboard_view(request):
    dg.glue_query_set(
        request,
        'test_query_1',
        TestGlueModelObject.objects.filter(id__gte=1).filter(id__lte=10000),
        exclude=('anniversary_datetime', 'birth_date'),
    )
    dg.glue_query_set(
        request,
        'test_query_2',
        TestGlueModelObject.objects.filter(id__gte=1).filter(id__lte=10000),
        'change',
        exclude=('birth_date', 'anniversary_datetime')
    )

    context_data = {}

    return TemplateResponse(
        request,
        template='glue_queryset/page/list_page.html',
        context=context_data
    )
