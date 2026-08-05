# Field Filtering

## Overview

Field filtering controls which model fields are exposed to the frontend. You must specify either `fields` to whitelist specific fields or `exclude` to blacklist them.

## Whitelist with `fields`

The `fields` parameter restricts the glue object to only the specified fields:

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

## Using `ALL_FIELDS`

Use the `ALL_FIELDS` constant to explicitly include or exclude all fields:

```python
from django_glue import Glue, GlueAccess, ALL_FIELDS

# Include all fields
Glue.model(
    request=request,
    unique_name='task',
    target=task,
    access=GlueAccess.CHANGE,
    fields=ALL_FIELDS,
)

# Exclude all model fields (useful when you only want form fields)
Glue.model(
    request=request,
    unique_name='task',
    target=task,
    access=GlueAccess.CHANGE,
    exclude=ALL_FIELDS,
)
```

## Using Both `fields` and `exclude`

When both are provided, `fields` restricts the candidate set, then `exclude` removes fields from it:

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

    Either `fields` or `exclude` must be provided. If you provide neither, a `ValueError` is raised.

## Field Filtering on QuerySet Glue

Field filtering works the same way on queryset glue:

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

When you include a ForeignKey or ManyToMany field in `fields`, the glue object will serialize the related data:

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

When you provide a `form` or `forms` parameter, the field filtering is derived from the form's fields combined with the glue `fields`/`exclude` settings:

```python
from myapp.forms import TaskSummaryForm

Glue.model(
    request=request,
    unique_name='task',
    target=task,
    access=GlueAccess.CHANGE,
    fields=['id', 'title'],
    form=TaskSummaryForm,
)
```

The `fields` and `exclude` parameters further restrict the exposed fields.

## Primary Key is Always Included

The primary key (`id`) is always included in the field definitions, even if you don't explicitly list it. This is necessary for the glue object to identify the model instance.

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

Exclude sensitive fields while allowing access to the rest:

```python
Glue.model(
    request=request,
    unique_name='user_profile',
    target=user,
    access=GlueAccess.CHANGE,
    exclude=['password', 'last_login', 'user_permissions'],
)
```
