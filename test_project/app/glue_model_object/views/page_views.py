from django.template.response import TemplateResponse

from test_project.app.glue_model_object import models

def list_view(request):

    context_data = {
        'glue_model_object_list' : models.TestGlueModelObject.objects.active()
    }

    return TemplateResponse(
        request,
        template='glue_model_object/page/list_page.html',
        context=context_data
    )
