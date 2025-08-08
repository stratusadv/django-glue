from django.template.response import TemplateResponse

import django_glue as dg


def dashboard_view(request):

    context_data = {}

    return TemplateResponse(
        request,
        template='glue_function/page/dashboard_page.html',
        context=context_data
    )
