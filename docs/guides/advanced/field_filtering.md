# Field Filtering

## Overview

Field filtering controls which model fields are exposed to the frontend. By default, all model fields are available. Use `fields` to whitelist specific fields or `exclude` to blacklist them.

## Whitelist with `fields`

The `fields` parameter restricts the proxy to only the specified fields:

```python
from django_glue import Glue, GlueAccess

Glue.model(
    request=request,
    unique_name='task',
    target=task,
    access=GlueAccess.CHANGE,
    fields=['id', 'title', 'done'],
)
```

Only `id`, `title`, and `done` can be read or written from the frontend. All other fields are invisible.

## Blacklist with `exclude`

The `exclude` parameter hides specific fields while exposing everything else:

```python
Glue.model(
    request=request,
    unique_name='task',
    target=task,
    access=GlueAccess.CHANGE,
    exclude=['password', 'internal_notes', 'api_key'],
)
```

## Using Both `fields` and `exclude`

When both are provided, `fields` restricts the candidate set, then `exclude` removes fields from it. Both parameters are applied independently to the model fields and the form fields, then the results are merged:

```python
Glue.model(
    request=request,
    unique_name='task',
    target=task,
    access=GlueAccess.CHANGE,
    fields=['id', 'title', 'description', 'done', 'priority'],
    exclude=['priority'],  # priority is removed from the allowed set
)
```

!!! note

    The `fields` and `exclude` parameters are applied to both the model fields (via `_model_field_definitions`) and the form fields (via `modelform_factory`). The final field set is the union of both, so a field excluded from the model definitions could still appear if it's present in the form definitions.

## Field Filtering on QuerySet Proxies

Field filtering works the same way on QuerySet proxies:

```python
Glue.queryset(
    request=request,
    unique_name='tasks',
    target=Task.objects.all(),
    access=GlueAccess.CHANGE,
    fields=['id', 'title', 'done', 'created_at'],
)
```

Only the specified fields will be returned when you call `all()` or `queryWithParams()`.

## Related Fields

When you include a ForeignKey or ManyToMany field in `fields`, the proxy will serialize the related data:

```python
Glue.queryset(
    request=request,
    unique_name='tasks',
    target=Task.objects.select_related('assigned_to').prefetch_related('tags'),
    access=GlueAccess.CHANGE,
    fields=['id', 'title', 'assigned_to', 'tags'],
)
```

- **ForeignKey** fields return the nested object's exposed fields
- **ManyToMany** fields return a list of related object PKs

## Custom ModelForm with Field Filtering

When you provide a `form_class`, the field filtering is derived from the form's fields:

```python
from myapp.forms import TaskSummaryForm

Glue.model(
    request=request,
    unique_name='task',
    target=task,
    access=GlueAccess.CHANGE,
    form_class=TaskSummaryForm,  # Only form fields are exposed
)
```

The `fields` and `exclude` parameters further restrict the form's fields.

## Primary Key is Always Included

The primary key (`id`) is always included in the field definitions, even if you don't explicitly list it. This is necessary for the proxy to identify the model instance.

## Practical Use Cases

### Read-Only Summary View

Expose only display fields for a summary view:

```python
Glue.model(
    request=request,
    unique_name='task_summary',
    target=task,
    access=GlueAccess.VIEW,
    fields=['id', 'title', 'done', 'created_at'],
)
```

### Edit Form with Restricted Fields

Allow editing only certain fields:

```python
Glue.model(
    request=request,
    unique_name='task',
    target=task,
    access=GlueAccess.CHANGE,
    fields=['id', 'title', 'description', 'done'],
)
```

### Hide Sensitive Data

Exclude sensitive fields while allowing full access to the rest:

```python
Glue.model(
    request=request,
    unique_name='user_profile',
    target=user,
    access=GlueAccess.CHANGE,
    exclude=['password', 'last_login', 'user_permissions'],
)
```
