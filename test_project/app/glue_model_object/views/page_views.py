from django.template.response import TemplateResponse

import django_glue as dg

from test_project.app.glue_model_object import models
from test_project.app.glue_model_object.utils import generate_randomized_test_model


def list_view(request):
    test_model_object = generate_randomized_test_model()

    dg.glue_model_object(
        request,
        'test_model_1',
        test_model_object,
        'delete',
        exclude=('birth_date', 'anniversary_datetime'),
        methods=['is_lighter_than', 'get_full_name']
    )

    context_data = {
        'glue_model_object_list' : models.TestGlueModelObject.objects.all()
    }

    return TemplateResponse(
        request,
        template='glue_model_object/page/list_page.html',
        context=context_data
    )
