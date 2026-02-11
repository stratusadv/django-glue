from django.http import HttpRequest
from django.shortcuts import render

import django_glue as dg
from test_project.task.models import Task


def task_detail_view(request: HttpRequest):
    task = Task.objects.first()

    if not task:
        task = Task.objects.create(
            title='test',
            description='test',
            done=False,
            order=1
        )

    dg.glue(
        request=request,
        target=task,
        unique_name='task',
        access=dg.GlueAccess.DELETE,
    )

    return render(request, 'detail_page.html', {'task': task})
