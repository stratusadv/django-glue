# Glue API

The `Glue` class is the central entry point for registering proxies in your Django views. Import it with:

```python
from django_glue import Glue, GlueAccess
```

## Methods

| Method | Proxy Type | Wraps |
|--------|------------|-------|
| `Glue.model()` | `GlueModelProxy` | Single Django model instance |
| `Glue.queryset()` | `GlueQuerySetProxy` | Django QuerySet collection |
| `Glue.collection()` | `GlueCollectionProxy` | Group of Glue objects |
| `Glue.form()` | `GlueModelProxy` or `GlueFormProxy` | Django ModelForm or regular Form |
| `Glue.template()` | `GlueTemplateProxy` | Django template by name |
| `Glue.function()` | `GlueFunctionProxy` | Python callable by dotted path |
| `Glue.json()` | `GlueJsonProxy` | Serializable dict, list, or primitive |

---

## `Glue.collection()`

Register a collection of Glue objects that should be grouped together.

```python
from django_glue import Glue, GlueAccess
from django_glue.glue.loading import LoadingStrategy

day_glues = [
    TimeEntryDayGlue(date=day.date, name=f'day_{i}', access=GlueAccess.CHANGE)
    for i, day in enumerate(days)
]

Glue.collection(
    request=request,
    unique_name='days',
    items=day_glues,
    access=GlueAccess.VIEW,
    loading_strategy=LoadingStrategy.EAGER,
)
```

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `request` | `HttpRequest` | Yes | The current request |
| `unique_name` | `str` | Yes | Unique identifier for this collection |
| `items` | `Iterable[BaseGlue]` | Yes | The Glue objects to include in the collection |
| `access` | `GlueAccess` | No | Access level (default: `VIEW`) |
| `loading_strategy` | `LoadingStrategy` | No | Loading behavior (default: `LAZY`) |

!!! warning "Lazy loading not supported"
    Collections do not yet support lazy loading. If you use `LoadingStrategy.LAZY` (the default), attempting to load the collection's state from the frontend will raise `CollectionLazyLoadNotSupportedError`. Use `LoadingStrategy.EAGER` to include the collection's state in the initial page manifest.

---

## `Glue.json()`

Register a serializable Python value (dict, list, or primitive) as frontend state.

```python
Glue.json(
    request=request,
    unique_name='config',
    target={'theme': 'dark', 'pageSize': 25},
    access=GlueAccess.VIEW,
)
```

Access on the frontend:

```javascript
console.log(Glue.json.config.theme)  // 'dark'
```

---

## Loading Strategy

All Glue shortcuts accept a `loading_strategy` parameter that controls when state is sent to the frontend.

```python
from django_glue.glue.loading import LoadingStrategy
```

| Strategy | Behavior |
|----------|----------|
| `LoadingStrategy.LAZY` | State is not included in the initial manifest. The frontend fetches it on first access. This is the **default**. |
| `LoadingStrategy.EAGER` | State is included in the initial manifest. No additional request is needed. |
| `LoadingStrategy.INHERIT` | Inherit the loading strategy from the parent Glue object (useful for nested objects). |

### When to use eager loading

Use `LoadingStrategy.EAGER` when:

- The data is needed immediately on page load (no loading spinner desired)
- The object is part of a collection that must load together
- You want to avoid the latency of a separate fetch request

```python
Glue.model(
    request=request,
    unique_name='task',
    target=task,
    access=GlueAccess.CHANGE,
    fields=['id', 'title', 'done'],
    loading_strategy=LoadingStrategy.EAGER,
)
```

---

## Related Field Configuration

The `related_field_config` parameter on `Glue.model()` and `Glue.queryset()` controls which fields are exposed on related objects (ForeignKey, OneToOne, reverse FK, and ManyToMany relationships).

```python
Glue.model(
    request=request,
    unique_name='time_entry',
    target=time_entry,
    access=GlueAccess.CHANGE,
    fields=['id', 'description', 'hours', 'project', 'user'],
    related_field_config={
        'project': {
            'fields': ['id', 'name', 'code'],
        },
        'user': {
            'fields': ['id', 'first_name', 'last_name'],
            'exclude': ['password', 'email'],
        },
    },
)
```

### Configuration options

Each related field name maps to a config dict with either `fields` or `exclude`:

| Key | Type | Description |
|-----|------|-------------|
| `fields` | `Sequence[str]` or `'__all__'` | Fields to include on the related object |
| `exclude` | `Sequence[str]` or `'__all__'` | Fields to exclude from the related object |

This is particularly useful for:

- Limiting exposed data on user objects (hiding email, password)
- Including display names alongside foreign key IDs
- Exposing nested object data without separate Glue registrations

### Frontend access

Related object fields are accessible as nested properties:

```javascript
const entry = Glue.model.time_entry
console.log(entry.project.name)       // 'Website Redesign'
console.log(entry.user.first_name)    // 'Alice'
```

---

## Source

::: django_glue.Glue
