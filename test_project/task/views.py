from django.http import HttpRequest
from django.shortcuts import render

import django_glue as dg
from test_project.task.models import Task


def page_view(request: HttpRequest):
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

    dg.glue(
        request=request,
        target=Task.objects.all(),
        unique_name='tasks',
        access=dg.GlueAccess.DELETE,
    )

    return render(request, 'page.html')
