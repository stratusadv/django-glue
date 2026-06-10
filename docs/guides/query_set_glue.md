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

### Using select_related and prefetch_related

For related model fields, use `select_related` (for ForeignKey) or `prefetch_related` (for ManyToMany) on your queryset. The proxy will automatically serialize the related fields:

```python
Glue.queryset(
    request=request,
    unique_name='tasks',
    target=Task.objects.select_related('assigned_to').prefetch_related('tags'),
    access=GlueAccess.CHANGE,
    fields=['id', 'title', 'assigned_to', 'tags'],
)
```

On the frontend, related objects are nested:

```javascript
const tasks = await Glue.querySet.tasks.all()
console.log(tasks[0].assigned_to.name)  // Nested FK object
console.log(tasks[0].tags)              // M2M as array of PKs
```

## Frontend: Using the QuerySet Proxy

### Fetching All Items

```javascript
const tasks = await Glue.querySet.tasks.all()
```

Each item is a full `GlueModelProxy` instance with its own methods:

```javascript
const tasks = await Glue.querySet.tasks.all()

// Access fields
console.log(tasks[0].title)

// Modify and save individual items
tasks[0].title = 'Updated Title'
await tasks[0].save()

// Delete individual items
await tasks[0].delete()
```

### Filtering

Use `queryWithParams()` to filter the queryset server-side:

```javascript
// Single condition
const activeTasks = await Glue.querySet.tasks.queryWithParams({
    filter: { done: false }
})

// Multiple conditions
const urgentTasks = await Glue.querySet.tasks.queryWithParams({
    filter: { done: false, priority: 2 }
})

// Django ORM lookups
const searchResults = await Glue.querySet.tasks.queryWithParams({
    filter: { title__icontains: 'search term' }
})
```

### Ordering

```javascript
const sortedTasks = await Glue.querySet.tasks.queryWithParams({
    order_by: ['title']
})

// Descending order
const sortedTasks = await Glue.querySet.tasks.queryWithParams({
    order_by: ['-created_at', 'title']
})
```

### Pagination with Slice

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

Build queries step by step using chainable methods. Set up the query parameters first, then call `all()` to execute:

```javascript
Glue.querySet.tasks
    .filter({ done: false })
    .orderBy(['-created_at'])
    .slice(0, 10)

const results = await Glue.querySet.tasks.all()
```

The chainable methods modify the internal query parameters. When you call `all()`, those parameters are sent to the server.

## Creating and Managing Items

### Creating a New Item

Add a new unsaved item to the queryset:

```javascript
// Add to the beginning
await Glue.querySet.tasks.prependNew()

// Add to the end
await Glue.querySet.tasks.appendNew()
```

The new item is a full model proxy with default values from the server:

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

When a child item is deleted, the parent queryset is automatically refreshed. No manual `refresh()` call is needed.

## Convenience Methods and Properties

| Method/Property | Description |
|-----------------|-------------|
| `all()` | Fetch all items using current query params |
| `queryWithParams(params)` | Fetch items with filter/order/slice params |
| `refresh()` | Clear cache and re-fetch with current params |
| `filter(params)` | Chainable: set filter params |
| `orderBy(params)` | Chainable: set order params |
| `slice(start, stop)` | Chainable: set slice params |
| `prependNew()` | Create new item at the start; returns updated `_items` |
| `appendNew()` | Create new item at the end; returns updated `_items` |
| `save(data)` | Save data via queryset action; auto-refreshes after |
| `delete(params)` | Delete items via queryset action; auto-refreshes after |
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

## Iteration

QuerySet proxies implement `Symbol.iterator`, so you can use `for...of`:

```javascript
const tasks = await Glue.querySet.tasks.all()
for (const task of tasks) {
    console.log(task.title)
}
```

!!! note

    `for...of` iteration doesn't work reliably in Alpine.js templates. Use the returned array directly in `x-for` loops.

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
    <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3/dist/cdn.min.js"></script>
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
            // Parent queryset auto-refreshes after child delete
            this.tasks = Glue.querySet.tasks._items
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

## Access Levels

| Access Level | Available Actions |
|-------------|-------------------|
| `VIEW` | `query_with_params()`, `get()`, `new()`, `foreign_key_choices()` |
| `CHANGE` | All VIEW actions + `validate()`, `save()` |
| `DELETE` | All CHANGE actions + `delete()` |
