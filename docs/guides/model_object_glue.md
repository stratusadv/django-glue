# Model Proxy Guide

## Purpose

Model proxies allow you to access and modify a single Django model instance from JavaScript. You can read fields, update values, save changes, and delete the instance — all through a transparent proxy object.

### When to Use

- When you need to read or edit a specific model instance from the frontend.
- When you want to perform CRUD operations on a model without writing custom API endpoints.

### When Not to Use

- When you only need read-only access to a model's fields. In that case, pass the data directly in your view context.
- When you need to work with multiple instances. Use a [QuerySet proxy](query_set_glue.md) instead.

## Backend: Registering a Model Proxy

Use `Glue.model()` in your Django view to register a model instance:

```python
from django_glue import Glue, GlueAccess
from myapp.models import Task

def task_view(request, pk):
    task = Task.objects.get(pk=pk)

    Glue.model(
        request=request,
        unique_name='task',
        target=task,
        access=GlueAccess.CHANGE,
    )

    return render(request, 'task_view.html')
```

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `request` | `HttpRequest` | Yes | The current request |
| `unique_name` | `str` | Yes | Unique identifier for the proxy |
| `target` | `Model` | Yes | The model instance to proxy |
| `access` | `GlueAccess` | No | Access level (default: `VIEW`) |
| `fields` | `Sequence` | No | Fields to include. Empty means all fields |
| `exclude` | `Sequence[str]` | No | Fields to exclude |
| `form_class` | `type[ModelForm]` | No | Custom ModelForm for validation |

### Field Filtering

Control which fields are exposed to the frontend:

```python
# Only expose specific fields
Glue.model(
    request=request,
    unique_name='task',
    target=task,
    access=GlueAccess.CHANGE,
    fields=['id', 'title', 'done'],
)

# Exclude sensitive fields
Glue.model(
    request=request,
    unique_name='task',
    target=task,
    access=GlueAccess.CHANGE,
    exclude=['password', 'internal_notes'],
)
```

### Custom Form Class

Provide a custom ModelForm for field-level validation:

```python
from myapp.forms import TaskForm

Glue.model(
    request=request,
    unique_name='task',
    target=task,
    access=GlueAccess.CHANGE,
    form_class=TaskForm,
)
```

## Frontend: Using the Model Proxy

Access the proxy as a property of the global `Glue.model` object using the unique name:

```javascript
// Glue.model.task is the model proxy
```

### Reading Fields

Access fields as properties. The proxy automatically fetches data on first access if not already loaded:

```javascript
// Lazy loading - fetches from server on first access
const title = Glue.model.task.title
const done = Glue.model.task.done
```

Explicitly fetch all field values:

```javascript
await Glue.model.task.get()
console.log(Glue.model.task.title)
```

### Updating Fields

Set field values directly:

```javascript
Glue.model.task.title = 'New Title'
Glue.model.task.done = true
```

### Saving Changes

After modifying fields, call `save()` to persist changes:

```javascript
Glue.model.task.title = 'Updated Title'
const result = await Glue.model.task.save()
```

### Deleting the Instance

```javascript
await Glue.model.task.delete()
```

### Checking if New

The `_isNew` property indicates whether the instance has been saved to the database:

```javascript
if (Glue.model.task._isNew) {
    console.log('This is a new, unsaved instance')
}
```

## Full Example: Editable Task Form

### Backend

```python
from django.shortcuts import render
from django_glue import Glue, GlueAccess
from myapp.models import Task

def task_edit_view(request, pk):
    task = Task.objects.get(pk=pk)

    Glue.model(
        request=request,
        unique_name='task',
        target=task,
        access=GlueAccess.CHANGE,
    )

    return render(request, 'tasks/edit.html')
```

### Frontend

```html
{% load django_glue %}
<!DOCTYPE html>
<html>
<head>
    <title>Edit Task</title>
</head>
<body>
    <div x-data="{
        loaded: false,
        saving: false,
        async init() {
            await Glue.model.task.get()
            this.loaded = true
        },
        async saveTask() {
            this.saving = true
            const result = await Glue.model.task.save()
            this.saving = false
            if (result.success) {
                alert('Task saved!')
            }
        }
    }">
        <input x-model="Glue.model.task.title" placeholder="Task title">
        <label>
            <input type="checkbox" x-model="Glue.model.task.done">
            Done
        </label>
        <button @click="saveTask()" :disabled="saving">
            Save
        </button>
    </div>

    {% django_glue_init %}
</body>
</html>
```

## Event Listeners

Attach listeners to proxy actions for reactive UI patterns:

```javascript
// Before save
Glue.model.task.addListener('save', (event) => {
    console.log('About to save:', event.payload)
}, 'before')

// After save
Glue.model.task.addListener('save', (event) => {
    console.log('Saved successfully:', event.result)
}, 'after')

// On error
Glue.model.task.addListener('save', (event) => {
    console.error('Save failed:', event.error)
}, 'error')
```

## Field Metadata

Each field exposes metadata through the `$fields` property:

```javascript
// Access field definitions
const titleField = Glue.model.task.$fields.title
console.log(titleField.label)      // Field label
console.log(titleField.required)   // Is field required
console.log(titleField.type)       // Django form field type
console.log(titleField.max_length) // Max length (if applicable)
```

## Access Levels

| Access Level | Available Actions |
|-------------|-------------------|
| `VIEW` | `get()`, `foreign_key_choices()` |
| `CHANGE` | All VIEW actions + `validate()`, `save()` |
| `DELETE` | All CHANGE actions + `delete()` |
