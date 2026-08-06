# Model Glue Guide

## Purpose

Model glue allows you to access and modify a single Django model instance from JavaScript. You can read fields, update values, save changes, and delete the instance — all through a transparent JavaScript object bound to your Django model.

### When to Use

- When you need to read or edit a specific model instance from the frontend.
- When you want to perform CRUD operations on a model without writing custom API endpoints.

### When Not to Use

- When you only need read-only access to a model's fields. Pass the data directly in your view context.
- When you need to work with multiple instances. Use [QuerySet glue](query_set_glue.md) instead.

## Backend: Registering a Model

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
        exclude=['internal_notes'],  # Expose all fields except internal_notes
    )

    return render(request, 'task_view.html')
```

### Parameters

| Parameter          | Type                        | Required | Description                                              |
| ------------------ | --------------------------- | -------- | -------------------------------------------------------- |
| `request`        | `HttpRequest`             | Yes      | The current request                                      |
| `unique_name`    | `str`                     | Yes      | Unique identifier for this glue object in the session    |
| `target`         | `Model`                   | Yes      | The model instance to expose                             |
| `access`         | `GlueAccess`              | No       | Access level (default:`VIEW`)                          |
| `fields`         | `Sequence[str]`           | Yes*     | Field names to include. Use`ALL_FIELDS` for all fields |
| `exclude`        | `Sequence[str]`           | Yes*     | Field names to exclude. Use`ALL_FIELDS` to exclude all |
| `form`           | `ModelForm`               | No       | Default ModelForm for validation                         |
| `forms`          | `Mapping[str, ModelForm]` | No       | Named ModelForms (e.g.,`{'edit': EditForm}`)           |
| `select_related` | `Sequence[str]`           | No       | ForeignKey fields to preload with select_related         |

*Either `fields` or `exclude` must be provided. You can import `ALL_FIELDS` from `django_glue` (or just enter '__all__'):

```python
from django_glue import ALL_FIELDS

Glue.model(
    request=request,
    unique_name='task',
    target=task,
    access=GlueAccess.CHANGE,
    fields=ALL_FIELDS,  # Include all fields
)
```

## Frontend: Using the Model

Access the model as a property of the global `Glue.model` object using the unique name you provided:

```javascript
// If you registered with unique_name='task':
Glue.model.task
```

### Reading Fields

Access fields as properties. The glue object automatically fetches data on first access if not already loaded:

```javascript
// Lazy loading — fetches from server on first field access
const title = Glue.model.task.title
const done = Glue.model.task.done
```

You can also explicitly fetch all field values:

```javascript
await Glue.model.task.load()
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
    errors: {}
}
```

Or on validation failure:

```javascript
{
    success: false,
    errors: { title: ['This field is required.'] }
}
```

### Deleting the Instance

```javascript
await Glue.model.task.delete()
```

For existing instances, `delete()` removes the instance from the database. For unsaved instances (`_isNew` is `true`) that belong to a parent queryset, it removes the item locally without making a server request.

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

## Computed Attributes

Use `computed_attributes` when the frontend needs readonly data calculated from the model instance.

```python
from django_glue import Glue, GlueAccess
from myapp.permissions import generate_permission_data

Glue.model(
    request=request,
    unique_name='group',
    target=group,
    access=GlueAccess.VIEW,
    fields=['id', 'name'],
    computed_attributes={
        'permission_data': (generate_permission_data, {'with_special_role': True}),
    },
)
```

The callable receives the model instance. Its return value is exposed as a readonly attribute:

```javascript
await Glue.model.group.load()
console.log(Glue.model.group.permission_data)
```

!!! note

    Computed attributes are not model fields and are not persisted by `save()`.

## Custom Forms

Provide a custom ModelForm to add field-level validation, custom widgets, or additional fields. You can pass either a form class or a form instance:

```python
from myapp.forms import TaskForm

# Pass a form class (simplest)
Glue.model(
    request=request,
    unique_name='task',
    target=task,
    access=GlueAccess.CHANGE,
    fields=['id', 'title', 'done'],
    form=TaskForm,
)

# Or pass a form instance (useful for custom initial data)
Glue.model(
    request=request,
    unique_name='task',
    target=task,
    access=GlueAccess.CHANGE,
    fields=['id', 'title', 'done'],
    form=TaskForm(initial={'priority': 'high'}),
)
```

You can also provide multiple named forms using the `forms` parameter:

```python
from myapp.forms import TaskEditForm, TaskQuickUpdateForm

Glue.model(
    request=request,
    unique_name='task',
    target=task,
    access=GlueAccess.CHANGE,
    fields=['id', 'title', 'done', 'description'],
    forms={
        'default': TaskEditForm,
        'quick': TaskQuickUpdateForm,
    },
)
```

The `default` form is used for validation during `save()`. Named forms are accessible via `forms.<name>` on the frontend.

!!! note

    When you pass a form class, an instance is created automatically. When you pass a form instance, it will be rebound to the model instance internally. You cannot use both `form` and `forms['default']` at the same time.

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
const choices = await brandField.choices
// Returns: [{pk: 1, __str__: "Brand A"}, {pk: 2, __str__: "Brand B"}, ...]
```

Choices are cached to avoid duplicate requests.

## Event Listeners

Attach listeners to actions for reactive UI patterns. Each action supports three event types: `'before'`, `'after'`, and `'error'`.

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
from django_glue import Glue, GlueAccess, ALL_FIELDS
from myapp.models import Task

def task_edit_view(request, pk):
    task = Task.objects.get(pk=pk)

    Glue.model(
        request=request,
        unique_name='task',
        target=task,
        access=GlueAccess.CHANGE,
        fields=ALL_FIELDS,
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
            await Glue.model.task.load()
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

| Access Level | Available Actions                     |
| ------------ | ------------------------------------- |
| `VIEW`     | `load()`, `foreign_key_choices()` |
| `CHANGE`   | All VIEW actions +`save()`          |
| `DELETE`   | All CHANGE actions +`delete()`      |
