from django.http import HttpRequest

import django_glue as dg
from test_project.task.models import Task


def task_list_view(request: HttpRequest):
    new_model = Task.objects.create()

    dg.glue_model_object(
        model_object=new_model,
        access='read',
    )
