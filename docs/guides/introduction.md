# Guides

## Before You Get Started

- Make sure you have a solid understanding of how Django works.
- Familiarity with JavaScript async/await patterns is recommended.

!!! warning

    Follow the [installation instructions](../getting_started/installation.md) before using these guides.

## What These Guides Cover

Each guide demonstrates:

- The purpose of the feature and when to use it.
- How to use the feature in both the backend (Python) and frontend (JavaScript).
- Practical examples with code.

!!! note

    These guides focus on the core concepts and common patterns. For complete API references, see the [API documentation](../api/).

## Core Concepts

### The Proxy Pattern

Django Glue creates proxy objects that act as transparent interfaces between Django objects and JavaScript. Each proxy:

1. Has a **unique name** identifying it in the session
2. Wraps a **target** (Model instance, QuerySet, or Form)
3. Has an **access level** (VIEW, CHANGE, or DELETE)
4. Exposes **actions** callable from JavaScript

### Proxy Types

| Proxy Type | Python Shortcut | JS Class | Wraps |
|------------|----------------|----------|-------|
| Model | `Glue.model()` | `GlueModelProxy` | Single Django model instance |
| QuerySet | `Glue.queryset()` | `GlueQuerySetProxy` | Django QuerySet collection |
| Form | `Glue.form()` | `GlueFormProxy` | Django Form instance |

### Access Control

```python
from django_glue import Glue, GlueAccess

# Permission cascade: DELETE > CHANGE > VIEW
GlueAccess.VIEW    # Read-only access
GlueAccess.CHANGE  # Read + write (includes VIEW)
GlueAccess.DELETE  # Read + write + delete (includes CHANGE)
```

### Frontend Access

Proxies are accessed as properties of the global `Glue` object:

```javascript
// Model proxy
Glue.model.task.title = 'New Title'
await Glue.model.task.save()

// QuerySet proxy
const tasks = await Glue.querySet.tasks.all()

// Form proxy
Glue.form.contact_form.name = 'John'
const result = await Glue.form.contact_form.validate()
```
