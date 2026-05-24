# Model Proxy Guide

## Purpose

Model proxies allow you to access and modify a single Django model instance from JavaScript. You can read fields, update values, save changes, and delete the instance — all through a transparent proxy object.

### When to Use

- When you need to read or edit a specific model instance from the frontend.
- When you want to perform CRUD operations on a model without writing custom API endpoints.

### When Not to Use

- When you only need read-only access to a model's fields. Pass the data directly in your view context.
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
| `unique_name` | `str` | Yes | Unique identifier for the proxy in the session |
| `target` | `Model` | Yes | The model instance to proxy |
| `access` | `GlueAccess` | No | Access level (default: `VIEW`) |
| `fields` | `Sequence` | No | Field names to include. Empty means all fields |
| `exclude` | `Sequence[str]` | No | Field names to exclude |
| `form_class` | `type[ModelForm]` | No | Custom ModelForm for validation |

## Frontend: Using the Model Proxy

Access the proxy as a property of the global `Glue.model` object using the unique name you provided:

```javascript
// If you registered with unique_name='task':
Glue.model.task
```

### Reading Fields

Access fields as properties. The proxy automatically fetches data on first access if not already loaded:

```javascript
// Lazy loading — fetches from server on first field access
const title = Glue.model.task.title
const done = Glue.model.task.done
```

You can also explicitly fetch all field values:

```javascript
await Glue.model.task.get()
console.log(Glue.model.task.title)
```

### Updating Fields

Set field values directly:

```javascript
Glue.model.task.title = 'New Title'
Glue.model.task.done = true
Glue.model.task.priority = 2
```

### Saving Changes

After modifying fields, call `save()` to persist changes to the database:

```javascript
Glue.model.task.title = 'Updated Title'
const result = await Glue.model.task.save()

if (result.success) {
    console.log('Saved successfully')
} else {
    console.log('Validation errors:', result.errors)
}
```

The save response follows this shape:

```javascript
{
    success: true,
    errors: null,
    cleaned_data: { title: 'Updated Title', done: false, priority: 2 }
}
```

### Deleting the Instance

```javascript
const result = await Glue.model.task.delete()
```

For existing instances, `delete()` returns the server response. For unsaved instances (`_isNew` is `true`) that belong to a parent queryset, it returns `{success: true}` without making a server request.

### Checking if the Instance is New

The `_isNew` property returns `true` if the instance hasn't been saved to the database yet (no primary key):

```javascript
if (Glue.model.task._isNew) {
    console.log('This is a new, unsaved instance')
}
```

## Field Filtering

Control which fields are exposed to the frontend by using the `fields` or `exclude` parameters:

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

Fields that are not exposed cannot be read or written from the frontend.

## Custom Form Class

Provide a custom ModelForm to add field-level validation, custom widgets, or additional fields:

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

The proxy uses your custom ModelForm for all validation during `save()` and `validate()` actions.

## Field Metadata

Each field exposes metadata through the `$fields` property. This is useful for building dynamic forms:

```javascript
// Access field definitions
const titleField = Glue.model.task.$fields.title
console.log(titleField.label)       // 'Title'
console.log(titleField.required)    // true
console.log(titleField.type)        // 'CharField'
console.log(titleField.max_length)  // 200
console.log(titleField.help_text)   // null or help text string

// Field value and errors
console.log(titleField.value)       // current field value
console.log(titleField.has_errors)  // true if field has validation errors
console.log(titleField.error_text)  // error messages as string
```

### Foreign Key Choices

For fields that reference other models (ForeignKey, ManyToManyField), choices are loaded lazily:

```javascript
const brandField = Glue.model.task.$fields.brand
const choices = await brandField.choices()
// Returns: [[pk, "display name"], [pk, "display name"], ...]
```

Choices are cached across all proxy instances to avoid duplicate requests.

## Event Listeners

Attach listeners to proxy actions for reactive UI patterns. Each action supports three event types: `'before'`, `'after'`, and `'error'`.

```javascript
// Before save — runs before the request is sent
Glue.model.task.addListener('save', (event) => {
    console.log('About to save:', event.payload)
}, 'before')

// After save — runs after a successful response
Glue.model.task.addListener('save', (event) => {
    console.log('Saved successfully:', event.result)
}, 'after')

// On error — runs when the request fails
Glue.model.task.addListener('save', (event) => {
    console.error('Save failed:', event.error)
}, 'error')
```

Listeners are chainable:

```javascript
Glue.model.task
    .addListener('save', onSaveSuccess, 'after')
    .addListener('save', onSaveError, 'error')
    .addListener('delete', onDelete, 'after')
```

Remove specific listeners:

```javascript
Glue.model.task.removeListener('save', onSaveSuccess, 'after')
```

Clear all listeners:

```javascript
Glue.model.task.clearListeners()
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
    <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3/dist/cdn.min.js"></script>
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
            } else {
                alert('Validation errors: ' + JSON.stringify(result.errors))
            }
        }
    }">
        <template x-if="loaded">
            <div>
                <label>Title</label>
                <input x-model="Glue.model.task.title" placeholder="Task title">

                <label>
                    <input type="checkbox" x-model="Glue.model.task.done">
                    Done
                </label>

                <button @click="saveTask()" :disabled="saving">
                    Save
                </button>
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
| `VIEW` | `get()`, `foreign_key_choices()` |
| `CHANGE` | All VIEW actions + `validate()`, `save()` |
| `DELETE` | All CHANGE actions + `delete()` |
