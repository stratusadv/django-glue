# QuerySet Proxy Guide

## Purpose

QuerySet proxies allow you to work with collections of Django model instances from JavaScript. Each item returned from a queryset is a full model proxy with its own `save()` and `delete()` methods.

### When to Use

- When you need to display and edit a list of model instances.
- When you need to filter, order, or paginate data from the frontend.
- When items in a collection need their own CRUD operations.

### When Not to Use

- When you only need to display a static list. Use regular Django template context instead.
- When you only need one instance. Use a [Model proxy](model_object_glue.md) instead.

## Backend: Registering a QuerySet Proxy

Use `Glue.queryset()` in your Django view:

```python
from django_glue import Glue, GlueAccess
from myapp.models import Task

def task_list_view(request):
    Glue.queryset(
        request=request,
        unique_name='tasks',
        target=Task.objects.all(),
        access=GlueAccess.CHANGE,
    )

    return render(request, 'task_list.html')
```

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `request` | `HttpRequest` | Yes | The current request |
| `unique_name` | `str` | Yes | Unique identifier for the proxy |
| `target` | `QuerySet` | Yes | The queryset to proxy |
| `access` | `GlueAccess` | No | Access level (default: `VIEW`) |
| `fields` | `Sequence` | No | Fields to include. Empty means all fields |
| `exclude` | `Sequence[str]` | No | Fields to exclude |
| `form_class` | `type[ModelForm]` | No | Custom ModelForm for validation |

## Frontend: Using the QuerySet Proxy

### Fetching All Items

```javascript
const tasks = await Glue.querySet.tasks.all()
```

Each item is a full `GlueModelProxy` instance:

```javascript
const tasks = await Glue.querySet.tasks.all()
console.log(tasks[0].title)        // Access field
tasks[0].title = 'Updated'         // Modify field
await tasks[0].save()              // Save individual item
await tasks[0].delete()            // Delete individual item
```

### Filtering

Use `queryWithParams()` to filter the queryset:

```javascript
// Filter by a single condition
const activeTasks = await Glue.querySet.tasks.queryWithParams({
    filter: { done: false }
})

// Filter by multiple conditions
const urgentTasks = await Glue.querySet.tasks.queryWithParams({
    filter: { done: false, priority: 'high' }
})

// Use Django ORM lookups
const searchResults = await Glue.querySet.tasks.queryWithParams({
    filter: { title__icontains: 'search term' }
})
```

### Ordering

```javascript
const sortedTasks = await Glue.querySet.tasks.queryWithParams({
    order_by: ['title']
})

// Multiple fields, descending
const sortedTasks = await Glue.querySet.tasks.queryWithParams({
    order_by: ['-created_at', 'title']
})
```

### Slicing (Pagination)

```javascript
const page1 = await Glue.querySet.tasks.queryWithParams({
    slice: { start: 0, stop: 10 }
})

const page2 = await Glue.querySet.tasks.queryWithParams({
    slice: { start: 10, stop: 20 }
})
```

### Combining Query Parameters

```javascript
const results = await Glue.querySet.tasks.queryWithParams({
    filter: { done: false, title__icontains: 'urgent' },
    order_by: ['-created_at'],
    slice: { start: 0, stop: 10 }
})
```

### Chainable Query Building

Build queries step by step (note: chain methods before calling `all()` or `queryWithParams()`):

```javascript
Glue.querySet.tasks
    .filter({ done: false })
    .orderBy(['-created_at'])
    .slice(0, 10)

const results = await Glue.querySet.tasks.all()
```

## Modifying Items

### Saving an Individual Item

Each item from the queryset is a full model proxy:

```javascript
const tasks = await Glue.querySet.tasks.all()
tasks[0].title = 'New Title'
await tasks[0].save()
```

When you delete a child item, the parent queryset automatically refreshes.

### Creating a New Item

Add a new unsaved item to the queryset:

```javascript
// Add to the beginning
await Glue.querySet.tasks.prependNew()

// Add to the end
await Glue.querySet.tasks.appendNew()
```

The new item is a full model proxy with default values:

```javascript
await Glue.querySet.tasks.prependNew()
const newItem = Glue.querySet.tasks._items[0]
newItem.title = 'New Task'
await newItem.save()
```

### Deleting an Individual Item

```javascript
const tasks = await Glue.querySet.tasks.all()
await tasks[0].delete()
```

## Convenience Methods and Properties

| Method/Property | Description |
|-----------------|-------------|
| `all()` | Fetch all items using current query params |
| `refresh()` | Clear cache and re-fetch current query |
| `isEmpty` | Returns `true` if loaded and no items |
| `isLoaded` | Returns `true` if items have been fetched |

```javascript
await Glue.querySet.tasks.all()

if (Glue.querySet.tasks.isEmpty) {
    console.log('No tasks found')
}

if (Glue.querySet.tasks.isLoaded) {
    console.log('Tasks have been loaded')
}
```

## Full Example: Task List with CRUD

### Backend

```python
from django.shortcuts import render
from django_glue import Glue, GlueAccess
from myapp.models import Task

def task_list_view(request):
    Glue.queryset(
        request=request,
        unique_name='tasks',
        target=Task.objects.all(),
        access=GlueAccess.DELETE,
    )

    return render(request, 'tasks/list.html')
```

### Frontend

```html
{% load django_glue %}
<!DOCTYPE html>
<html>
<head>
    <title>Task List</title>
</head>
<body>
    <div x-data="{
        tasks: [],
        loading: false,
        async init() {
            this.loading = true
            this.tasks = await Glue.querySet.tasks.all()
            this.loading = false
        },
        async addTask() {
            await Glue.querySet.tasks.prependNew()
            this.tasks = Glue.querySet.tasks._items
        },
        async deleteTask(task) {
            await task.delete()
            this.tasks = await Glue.querySet.tasks.all()
        }
    }">
        <button @click="addTask()">Add Task</button>

        <template x-for="task in tasks" :key="task.$key">
            <div>
                <input x-model="task.title" placeholder="Task title">
                <label>
                    <input type="checkbox" x-model="task.done"> Done
                </label>
                <button @click="task.save()">Save</button>
                <button @click="deleteTask(task)">Delete</button>
            </div>
        </template>
    </div>

    {% django_glue_init %}
</body>
</html>
```

## Event Listeners

Attach listeners to actions on the queryset or individual items:

```javascript
// Listen for saves on any item in the queryset
Glue.querySet.tasks.addListener('save', (event) => {
    console.log('Item saved:', event.result)
}, 'after')

// Listen for deletes
Glue.querySet.tasks.addListener('delete', (event) => {
    console.log('Item deleted')
}, 'after')
```

Child proxy events bubble up to the parent queryset's listeners automatically.

## Access Levels

| Access Level | Available Actions |
|-------------|-------------------|
| `VIEW` | `query_with_params()`, `get()`, `new()`, `foreign_key_choices()` |
| `CHANGE` | All VIEW actions + `validate()`, `save()` |
| `DELETE` | All CHANGE actions + `delete()` |
