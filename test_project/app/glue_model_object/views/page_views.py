from django.template.response import TemplateResponse

from test_project.app.glue_model_object import models
from test_project.app.glue_model_object.utils import generate_randomized_test_model


def list_view(request):
    generate_randomized_test_model()

    context_data = {
        'glue_model_object_list' : models.TestGlueModelObject.objects.all()
    }

    return TemplateResponse(
        request,
        template='glue_model_object/page/list_page.html',
        context=context_data
    )
