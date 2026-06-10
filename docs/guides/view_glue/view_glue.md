# GlueView Guide

## Purpose

GlueView allows you to dynamically render HTML fragments from Django views and inject them into your page. When the rendered view registers new Glue proxies, they are automatically initialized on the client side.

### When to Use

- When you need to load content dynamically without a full page reload.
- When the loaded content contains its own Glue proxies that need to be initialized.
- When you want to separate context data for different sections of a page.

### When Not to Use

- When you only need to fetch JSON data. Use proxy actions directly instead.
- When the content is static and doesn't change. Include it in your template normally.

## How It Works

1. Create a `GlueView` with a target URL using `Glue.view(url)`.
2. Call a render method to fetch and insert the HTML.
3. The server renders the target view, captures any registered proxies, and returns the HTML along with proxy data.
4. The client automatically initializes any new proxies found in the response.

## Creating a GlueView

```javascript
const view = Glue.view('/path/to/view/')
```

You can also pass shared payload data that will be included with every request:

```javascript
const view = Glue.view('/path/to/view/', { sharedParam: 'value' })
```

## Render Methods

### renderInnerHtml

Replace the contents of an element:

```javascript
await view.renderInnerHtml(document.getElementById('target'), { param: 'value' })
```

### renderOuterHtml

Replace the element entirely:

```javascript
await view.renderOuterHtml(document.getElementById('target'), { param: 'value' })
```

### insertAdjacentHtml Methods

Insert HTML relative to an element:

```javascript
// Insert at the end of the element (after last child)
await view.renderInsertAdjacentHtmlBeforeEnd(target, { param: 'value' })

// Insert after the element
await view.renderInsertAdjacentHtmlAfterEnd(target, { param: 'value' })

// Insert before the element
await view.renderInsertAdjacentHtmlBeforeBegin(target, { param: 'value' })

// Insert at the beginning of the element (before first child)
await view.renderInsertAdjacentHtmlAfterBegin(target, { param: 'value' })
```

### Direct Fetch

Get the HTML string without inserting it:

```javascript
const html = await view.get({ param: 'value' })   // GET request
const html = await view.post({ param: 'value' })  // POST request
```

## Full Example

### Backend

**views.py**
```python
from django.shortcuts import render
from django.template.response import TemplateResponse
from django_glue import Glue, GlueAccess
from myapp.models import Task

def task_dashboard_view(request):
    """Main page that loads task details dynamically."""
    return render(request, 'tasks/dashboard.html')

def task_detail_view(request, pk):
    """View loaded dynamically via GlueView."""
    task = Task.objects.get(pk=pk)

    Glue.model(
        request=request,
        unique_name=f'task_{pk}',
        target=task,
        access=GlueAccess.CHANGE,
    )

    return TemplateResponse(request, 'tasks/_detail.html', {'task': task})
```

**urls.py**
```python
from django.urls import path
from . import views

urlpatterns = [
    path('tasks/', views.task_dashboard_view, name='dashboard'),
    path('tasks/<int:pk>/detail/', views.task_detail_view, name='detail'),
]
```

### Frontend

**dashboard.html**
```html
{% load django_glue %}
<!DOCTYPE html>
<html>
<head>
    <title>Task Dashboard</title>
    <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3/dist/cdn.min.js"></script>
</head>
<body>
    <div x-data="{
        selectedTaskId: 1,

        async loadTaskDetail(taskId) {
            const view = Glue.view(`/tasks/${taskId}/detail/`)
            await view.renderInnerHtml(document.getElementById('task-detail'))
        }
    }" x-init="loadTaskDetail(selectedTaskId)">
        <div>
            <button @click="loadTaskDetail(1)">Task 1</button>
            <button @click="loadTaskDetail(2)">Task 2</button>
            <button @click="loadTaskDetail(3)">Task 3</button>
        </div>

        <div id="task-detail">
            <!-- Task detail will be loaded here -->
        </div>
    </div>

    {% django_glue_init %}
</body>
</html>
```

**_detail.html**
```html
<div x-data="{
    async init() {
        await Glue.model.task_{{ task.pk }}.get()
    }
}">
    <h3 x-text="Glue.model.task_{{ task.pk }}.title"></h3>
    <p x-text="Glue.model.task_{{ task.pk }}.description"></p>
    <label>
        <input type="checkbox" x-model="Glue.model.task_{{ task.pk }}.done">
        Done
    </label>
    <button @click="Glue.model.task_{{ task.pk }}.save()">Save</button>
</div>
```

## Working with Payloads

Pass per-request payload data:

```javascript
const view = Glue.view('/tasks/detail/')

// Shared payload (sent with every request)
const view = Glue.view('/tasks/detail/', { format: 'compact' })

// Per-request payload (merged with shared payload)
await view.renderInnerHtml(target, { taskId: 5 })
```

## Automatically Initialized Proxies

When a GlueView renders a view that registers new proxies, those proxies are automatically available on the `Glue` object:

```javascript
// Before loading the view, Glue.model.task_1 doesn't exist
await view.renderInnerHtml(target)

// After loading, the proxy is available
await Glue.model.task_1.get()
```

## Render Method Comparison

| Method | Behavior | Use When |
|--------|----------|----------|
| `renderInnerHtml` | Replaces element's **contents** | Container has bindings you need to keep |
| `renderOuterHtml` | Replaces the **element entirely** | Response HTML defines the container |
| `renderInsertAdjacentHtmlBeforeEnd` | Inserts at end of element | Append content |
| `renderInsertAdjacentHtmlAfterEnd` | Inserts after element | Add sibling after |
| `renderInsertAdjacentHtmlBeforeBegin` | Inserts before element | Add sibling before |
| `renderInsertAdjacentHtmlAfterBegin` | Inserts at start of element | Prepend content |
| `get()` / `post()` | Returns HTML string | You want to handle insertion yourself |
