# Access Control

## Overview

Django Glue enforces permissions server-side on every action request. Each proxy is registered with an access level that determines which actions can be performed from the frontend.

## Access Levels

The `GlueAccess` enum defines three permission levels with a cascade:

| Level | Value | Can Perform |
|-------|-------|-------------|
| `VIEW` | `'view'` | Read-only actions (`get()`, `foreign_key_choices()`) |
| `CHANGE` | `'change'` | Read + write actions (`validate()`, `save()`) |
| `DELETE` | `'delete'` | All actions, including `delete()` |

The cascade means that a higher level includes all permissions from lower levels:
- `DELETE` includes `CHANGE` and `VIEW`
- `CHANGE` includes `VIEW`
- `VIEW` is read-only

## Registering Proxies with Access

```python
from django_glue import Glue, GlueAccess

# Read-only — frontend can only call get()
Glue.model(
    request=request,
    unique_name='task_readonly',
    target=task,
    access=GlueAccess.VIEW,
)

# Read + write — frontend can call get(), save(), validate()
Glue.model(
    request=request,
    unique_name='task_editable',
    target=task,
    access=GlueAccess.CHANGE,
)

# Full access — frontend can call get(), save(), validate(), delete()
Glue.model(
    request=request,
    unique_name='task_full',
    target=task,
    access=GlueAccess.DELETE,
)
```

## Per-Action Access Requirements

Each action method has a minimum required access level:

### Model Proxy

| Action | Required Access |
|--------|----------------|
| `get()` | `VIEW` |
| `validate()` | `CHANGE` |
| `save()` | `CHANGE` |
| `delete()` | `DELETE` |
| `foreign_key_choices()` | `VIEW` |

### QuerySet Proxy

| Action | Required Access |
|--------|----------------|
| `query_with_params()` | `VIEW` |
| `get()` | `VIEW` |
| `new()` | `VIEW` |
| `validate()` | `CHANGE` |
| `save()` | `CHANGE` |
| `delete()` | `DELETE` |
| `foreign_key_choices()` | `VIEW` |

### Form Proxy

| Action | Required Access |
|--------|----------------|
| `get()` | `VIEW` |
| `validate()` | `CHANGE` |
| `save()` | `CHANGE` |
| `foreign_key_choices()` | `VIEW` |

## What Happens on Access Violation

When the frontend attempts an action without sufficient access, the server raises a `GlueAccessError`. The error is returned as a JSON response with the error details:

```javascript
try {
    await Glue.model.task_readonly.save()
} catch (error) {
    // error contains details about the access violation
    console.error('Access denied:', error)
}
```

## Combining Access Control with Field Filtering

For fine-grained control, combine access levels with field filtering. A proxy with `CHANGE` access and a restricted `fields` list can only modify the specified fields:

```python
# User can edit title and done, but not priority or internal fields
Glue.model(
    request=request,
    unique_name='task',
    target=task,
    access=GlueAccess.CHANGE,
    fields=['id', 'title', 'done'],
)
```

## Dynamic Access Based on User

You can set the access level dynamically based on the requesting user:

```python
from django_glue import Glue, GlueAccess

def task_view(request, pk):
    task = Task.objects.get(pk=pk)

    # Owner gets full access, others get read-only
    if task.owner == request.user:
        access = GlueAccess.DELETE
    else:
        access = GlueAccess.VIEW

    Glue.model(
        request=request,
        unique_name='task',
        target=task,
        access=access,
    )

    return render(request, 'task.html')
```

## Using Glue.Access Shortcut

The `Glue` class provides `Glue.Access` as a convenience alias for `GlueAccess`:

```python
from django_glue import Glue

Glue.model(
    request=request,
    unique_name='task',
    target=task,
    access=Glue.Access.CHANGE,
)
```

This is equivalent to:

```python
from django_glue import Glue, GlueAccess

Glue.model(
    request=request,
    unique_name='task',
    target=task,
    access=GlueAccess.CHANGE,
)
```
