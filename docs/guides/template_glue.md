# Template Glue Guide

## Purpose

Template glue allows you to render Django templates from JavaScript with dynamic context data. You can inject rendered HTML into any DOM element using the same methods provided by `Glue.view`, but without needing a Django view function.

### When to Use

- When you need to render a template fragment with dynamic data from the frontend.
- When you want to update parts of the page with server-rendered HTML without writing a custom view.
- When you have a reusable template that should be rendered with different context data on demand.

### When Not to Use

- When the template needs to register its own glue objects. Use [GlueView](view_glue/view_glue.md) instead.
- When the content is static and doesn't change. Include it in your template normally.
- When you only need JSON data. Use model or queryset actions directly instead.

## Backend: Registering a Template

Use `Glue.template()` in your Django view to register a template:

```python
from django_glue import Glue

def my_view(request):
    Glue.template(
        request=request,
        unique_name='card',
        target='components/card.html',
        initial_context_data={'default_greeting': 'Hello'},
    )

    return render(request, 'my_view.html')
```

### Parameters

| Parameter              | Type   | Required | Description                                      |
| ---------------------- | ------ | -------- | ------------------------------------------------ |
| `request`              | `HttpRequest` | Yes | The current request                              |
| `unique_name`          | `str`  | Yes      | Unique identifier for this template glue object  |
| `target`               | `str`  | Yes      | Template name (e.g., `'components/card.html'`)   |
| `initial_context_data` | `dict` | No       | Default context data merged into every render    |

!!! note

    Template glue always uses `VIEW` access level internally, as rendering is a read-only operation.

## Frontend: Using the Template

Access the template as a property of the global `Glue.template` object using the unique name you provided:

```javascript
// If you registered with unique_name='card':
Glue.template.card
```

## Render Methods

All render methods accept a target DOM element and an optional payload of context data:

### renderInnerHtml

Replace the contents of an element:

```javascript
await Glue.template.card.renderInnerHtml(document.getElementById('target'), { name: 'John' })
```

### renderOuterHtml

Replace the element entirely:

```javascript
await Glue.template.card.renderOuterHtml(document.getElementById('target'), { name: 'Jane' })
```

### insertAdjacentHtml Methods

Insert HTML relative to an element:

```javascript
// Insert at the end of the element (after last child)
await Glue.template.card.renderInsertAdjacentHtmlBeforeEnd(target, { name: 'Bob' })

// Insert after the element
await Glue.template.card.renderInsertAdjacentHtmlAfterEnd(target, { name: 'Alice' })

// Insert before the element
await Glue.template.card.renderInsertAdjacentHtmlBeforeBegin(target, { name: 'Eve' })

// Insert at the beginning of the element (before first child)
await Glue.template.card.renderInsertAdjacentHtmlAfterBegin(target, { name: 'Charlie' })
```

## Context Data Merging

Context data flows through two layers, with later values overriding earlier ones:

1. **Backend `initial_context_data`** — set when registering the template in Python
2. **Per-call `payload`** — passed to each render method

```python
# Backend default context
Glue.template(
    request=request,
    unique_name='card',
    target='components/card.html',
    initial_context_data={
        'greeting': 'Hello',
        'theme': 'dark',
    },
)
```

```javascript
// Per-call payload overrides backend defaults
await Glue.template.card.renderInnerHtml(target, { greeting: 'Hi' })
// Template receives: { greeting: 'Hi', theme: 'dark' }
```

## Event Listeners

Template glue supports the same listener system as other glue objects:

```javascript
// Before render
Glue.template.card.addListener('render_html', (event) => {
    console.log('Rendering with:', event.payload)
}, 'before')

// After render
Glue.template.card.addListener('render_html', (event) => {
    console.log('Rendered HTML:', event.result)
}, 'after')

// On error
Glue.template.card.addListener('render_html', (event) => {
    console.error('Render failed:', event.error)
}, 'error')
```

## Full Example: Dynamic Card Component

### Backend

```python
from django.shortcuts import render
from django_glue import Glue

def dashboard_view(request):
    Glue.template(
        request=request,
        unique_name='task_card',
        target='tasks/_card.html',
        initial_context_data={'show_actions': True},
    )

    return render(request, 'tasks/dashboard.html')
```

### Template

```html
<!-- tasks/_card.html -->
<div class="task-card">
    <h3>{{ name }}</h3>
    <p>{{ description }}</p>
    {% if show_actions %}
    <button>Edit</button>
    {% endif %}
</div>
```

### Frontend

```html
{% load django_glue %}
<!DOCTYPE html>
<html>
<head>
    <title>Dashboard</title>
    <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3/dist/cdn.min.js"></script>
</head>
<body>
    <div x-data="{
        tasks: [
            { name: 'Design UI', description: 'Create wireframes' },
            { name: 'Write Tests', description: 'Unit tests for API' },
        ],
        selectedTask: null,

        async showCard(task) {
            this.selectedTask = task
            await Glue.template.task_card.renderInnerHtml(
                document.getElementById('card-container'),
                task
            )
        }
    }">
        <div class="task-list">
            <template x-for="task in tasks" :key="task.name">
                <button @click="showCard(task)" x-text="task.name"></button>
            </template>
        </div>

        <div id="card-container">
            <!-- Card will be rendered here -->
        </div>
    </div>

    {% django_glue_init %}
</body>
</html>
```

## Render Method Comparison

| Method                                | Behavior                           | Use When                          |
| ------------------------------------- | ---------------------------------- | --------------------------------- |
| `renderInnerHtml`                     | Replaces element's **contents**    | Container has bindings to keep    |
| `renderOuterHtml`                     | Replaces the **element entirely**  | Response HTML defines container   |
| `renderInsertAdjacentHtmlBeforeEnd`   | Inserts at end of element          | Append content                    |
| `renderInsertAdjacentHtmlAfterEnd`    | Inserts after element              | Add sibling after                 |
| `renderInsertAdjacentHtmlBeforeBegin` | Inserts before element             | Add sibling before                |
| `renderInsertAdjacentHtmlAfterBegin`  | Inserts at start of element        | Prepend content                   |

## Template Glue vs GlueView

| Feature             | `Glue.template`                                 | `Glue.view`                                             |
| ------------------- | ----------------------------------------------- | ------------------------------------------------------- |
| Target              | Template name string                            | Django view URL                                         |
| Registration        | Registered in session                           | Ad-hoc, per-call                                        |
| Context data        | Backend defaults + per-call merge               | View payload only                                       |
| Nested glue objects | Not supported                                   | Automatically initializes glue objects from rendered view |
| Use case            | Render a template with dynamic data             | Load a full view with embedded glue objects             |

Use `Glue.template` for simple template rendering with dynamic context. Use `Glue.view` when the rendered content contains its own glue objects that need initialization.
