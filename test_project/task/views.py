from django.http import HttpRequest
from django.shortcuts import render

from django_glue import Glue, GlueAccess
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

    Glue.model(
        request=request,
        target=task,
        unique_name='task',
        access=GlueAccess.DELETE,
    )

    Glue.queryset(
        request=request,
        target=Task.objects.all(),
        unique_name='tasks',
        access=GlueAccess.DELETE,
    )

    return render(request, 'page.html')
