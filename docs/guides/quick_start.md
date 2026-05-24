# Quick Start Tutorial

This tutorial walks you through building a complete task management page using Django Glue. By the end, you'll have a working page where users can view, edit, create, and delete tasks — all powered by Django Glue proxies.

## Prerequisites

- A Django project with `django_glue` installed and configured
- Familiarity with Django models, views, and templates

If you haven't set up Django Glue yet, follow the [Installation Guide](../getting_started/installation.md) first.

## Step 1: Create a Model

Start with a simple Task model:

```python
# tasks/models.py
from django.db import models


class Task(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    done = models.BooleanField(default=False)
    priority = models.IntegerField(default=0, help_text='0=low, 1=medium, 2=high')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title
```

Run migrations:

```bash
python manage.py makemigrations tasks
python manage.py migrate
```

## Step 2: Register Proxies in Your View

Create a view that registers both a QuerySet proxy (for the task list) and a Model proxy (for editing a single task):

```python
# tasks/views.py
from django.shortcuts import render
from django_glue import Glue, GlueAccess
from .models import Task


def task_dashboard(request):
    # QuerySet proxy for the task list
    Glue.queryset(
        request=request,
        unique_name='tasks',
        target=Task.objects.all(),
        access=GlueAccess.DELETE,
    )

    # Model proxy for a single task (e.g., for a detail form)
    task = Task.objects.first()
    if task:
        Glue.model(
            request=request,
            unique_name='selected_task',
            target=task,
            access=GlueAccess.CHANGE,
        )

    return render(request, 'tasks/dashboard.html')
```

Add the URL pattern:

```python
# tasks/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.task_dashboard, name='dashboard'),
]
```

## Step 3: Create the Template

Create a template that uses Alpine.js to interact with the proxies:

```html
<!-- templates/tasks/dashboard.html -->
{% load django_glue %}
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Task Dashboard</title>
    <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3/dist/cdn.min.js"></script>
    <style>
        body { font-family: system-ui, sans-serif; max-width: 800px; margin: 2rem auto; padding: 0 1rem; }
        .task-item { padding: 0.75rem; margin: 0.5rem 0; border: 1px solid #ddd; border-radius: 4px; display: flex; align-items: center; gap: 0.75rem; }
        .task-item.done { opacity: 0.6; }
        .task-item.done .task-title { text-decoration: line-through; }
        button { padding: 0.25rem 0.75rem; cursor: pointer; }
        input[type="text"] { padding: 0.25rem; flex: 1; }
    </style>
</head>
<body>
    <h1>Task Dashboard</h1>

    <div x-data="{
        tasks: [],
        loading: false,

        async init() {
            await this.loadTasks()
        },

        async loadTasks() {
            this.loading = true
            this.tasks = await Glue.querySet.tasks.all()
            this.loading = false
        },

        async addTask() {
            await Glue.querySet.tasks.prependNew()
            this.tasks = Glue.querySet.tasks._items
        },

        async saveTask(task) {
            const result = await task.save()
            if (!result.success) {
                alert('Save failed: ' + JSON.stringify(result.errors))
            }
        },

        async deleteTask(task) {
            await task.delete()
            // Parent queryset auto-refreshes after child delete
            this.tasks = Glue.querySet.tasks._items
        }
    }">
        <div style="margin-bottom: 1rem;">
            <button @click="addTask()">+ Add Task</button>
            <button @click="loadTasks()" :disabled="loading">Refresh</button>
        </div>

        <template x-if="loading">
            <p>Loading tasks...</p>
        </template>

        <template x-for="task in tasks" :key="task.$key">
            <div class="task-item" :class="{ done: task.done }">
                <input type="checkbox"
                       x-model="task.done"
                       @change="saveTask(task)">

                <input type="text"
                       class="task-title"
                       x-model="task.title"
                       @blur="saveTask(task)"
                       placeholder="Task title">

                <span x-text="'Priority: ' + task.priority"></span>

                <button @click="deleteTask(task)">Delete</button>
            </div>
        </template>
    </div>

    {% django_glue_init %}
</body>
</html>
```

## Step 4: Test It

Run the development server and visit your dashboard URL. You should be able to:

1. **View tasks** — The task list loads automatically on page load
2. **Create tasks** — Click "+ Add Task" to add a new blank task, then type a title and click away to save
3. **Edit tasks** — Change the title or toggle the done checkbox, then click away to save
4. **Delete tasks** — Click the Delete button on any task

## How It Works

Let's trace what happens when you toggle a task's done checkbox:

1. Alpine.js updates `task.done` via the property setter on the `GlueModelProxy`
2. When you click away (`@blur`), `saveTask(task)` is called
3. The proxy sends a POST to `/__dg__/action/tasks/save/` with the field data
4. Django validates the data using a ModelForm, persists the changes, and returns the result
5. The result is returned to Alpine.js, which can react to success or errors

## What You've Learned

- **`Glue.queryset()`** — Register a QuerySet proxy for working with collections
- **`Glue.model()`** — Register a Model proxy for a single instance
- **`GlueAccess.DELETE`** — Grants full CRUD permissions (VIEW + CHANGE + DELETE)
- **`Glue.querySet.tasks.all()`** — Fetch all items from a QuerySet proxy
- **`Glue.querySet.tasks.prependNew()`** — Create a new unsaved item at the start of the list
- **`task.save()`** — Persist changes on a model proxy
- **`task.delete()`** — Delete a model instance

## Next Steps

Now that you have the basics, explore:

- **[Model Proxy Guide](model_object_glue.md)** — Field filtering, custom forms, lazy loading, and field metadata
- **[QuerySet Proxy Guide](query_set_glue.md)** — Filtering, ordering, pagination, and chainable queries
- **[Form Proxy Guide](form_glue.md)** — Regular forms, ModelForms, and validation
- **[GlueView Guide](view_glue/view_glue.md)** — Dynamically loading HTML fragments
- **[Advanced Topics](advanced/access_control.md)** — Access control, event listeners, field filtering, and configuration
