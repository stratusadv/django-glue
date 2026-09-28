# Quick start

This example adds an editable task list to a Django page. Complete the
[installation steps](../getting_started/installation.md) first.

## Model and view

```python
from django.db import models


class Task(models.Model):
    title = models.CharField(max_length=200)
    done = models.BooleanField(default=False)
```

After migrating the model, register a queryset in the page view:

```python
from django.shortcuts import render
from django_glue import Glue

from .models import Task


def task_dashboard(request):
    Glue.queryset(
        request=request,
        target=Task.objects.all(),
        unique_name='tasks',
        access=Glue.Access.DELETE,
        fields=['id', 'title', 'done'],
        editable=['title', 'done'],
    )
    return render(request, 'tasks/dashboard.html')
```

`DELETE` includes `CHANGE` and `ADD`, so this page can edit, create, and
delete tasks. Choose a narrower access level for pages that need less.

## Template

```django
{% load django_glue %}
<!doctype html>
<html>
<head><title>Tasks</title></head>
<body>
    <div x-data="{
        tasks: Glue.querySet.tasks,
        async init() { await this.tasks.all() },
        async addTask() {
            const task = await this.tasks.new({title: 'New task'})
            await task.save()
            await this.tasks.refresh()
        },
        async deleteTask(task) {
            await task.delete()
            await this.tasks.refresh()
        }
    }">
        <button @click="addTask()">Add task</button>
        <template x-for="task in tasks.items" :key="task.$key">
            <div>
                <input x-model="task.title" @change="task.save()">
                <input type="checkbox" x-model="task.done" @change="task.save()">
                <button @click="deleteTask(task)">Delete</button>
            </div>
        </template>
    </div>
    {% django_glue_init %}
</body>
</html>
```

The initial queryset entry has no rows. `all()` fetches them through the
shared addressed request endpoint. Each row has its own proxy and signed
policy. A field edit remains local until `save()` acknowledges it; `refresh()`
re-runs the queryset after membership changes.

Continue with [model objects](model_object_glue.md),
[querysets](query_set_glue.md), [forms](form_glue.md), and
[components](components.md).
