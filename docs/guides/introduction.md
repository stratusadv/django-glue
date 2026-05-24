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

    These guides focus on the core concepts and common patterns. For complete API references, see the [API documentation](../api/glue/shortcuts.md).

## Core Concepts

### The Proxy Pattern

Django Glue creates proxy objects that act as transparent interfaces between Django objects and JavaScript. Each proxy:

1. Has a **unique name** identifying it in the session
2. Wraps a **target** (Model instance, QuerySet, Form, Template, or Function)
3. Has an **access level** (VIEW, CHANGE, or DELETE)
4. Exposes **actions** callable from JavaScript

### The Glue Shortcut API

All proxy registration goes through the `Glue` class:

```python
from django_glue import Glue, GlueAccess
```

| Method | Proxy Type | Wraps |
|--------|------------|-------|
| `Glue.model()` | `GlueModelProxy` | Single Django model instance |
| `Glue.queryset()` | `GlueQuerySetProxy` | Django QuerySet collection |
| `Glue.form()` | `GlueModelProxy` or `GlueFormProxy` | Django ModelForm or regular Form |
| `Glue.template()` | `GlueTemplateProxy` | Django template by name |
| `Glue.function()` | `GlueFunctionProxy` | Python callable by dotted path |

On the frontend, proxies are accessed through the global `Glue` object:

| Namespace | Proxy Type | Example |
|-----------|------------|---------|
| `Glue.model` | Model proxies | `Glue.model.task` |
| `Glue.querySet` | QuerySet proxies | `Glue.querySet.tasks` |
| `Glue.form` | Form proxies | `Glue.form.contact_form` |
| `Glue.template` | Template proxies | `Glue.template.card` |
| `Glue.function` | Function proxies | `await Glue.function.calculate(10, 20)` |

### Access Control

```python
from django_glue import Glue, GlueAccess

# Permission cascade: DELETE > CHANGE > VIEW
GlueAccess.VIEW    # Read-only access
GlueAccess.CHANGE  # Read + write (includes VIEW)
GlueAccess.DELETE  # Read + write + delete (includes CHANGE)
```

Access is enforced server-side on every action request. A proxy registered with `CHANGE` can perform any `VIEW` action, and a proxy with `DELETE` can perform any `CHANGE` or `VIEW` action.

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

// Template proxy
await Glue.template.card.renderInnerHtml(document.getElementById('card'), { name: 'John' })

// Function proxy
const total = await Glue.function.calculateTotal(100, 0.08, true)
```

### GlueView

For dynamically loading HTML fragments from Django views:

```javascript
const view = Glue.view('/path/to/view/')
await view.renderInnerHtml(document.getElementById('target'), { param: 'value' })
```

See the [GlueView Guide](view_glue/view_glue.md) for details.

## How Requests Flow

Understanding the request lifecycle helps with debugging:

1. **Page load**: Your Django view calls `Glue.model()` (etc.) to register proxies. The `{% django_glue_init %}` template tag injects the JS client with proxy metadata.
2. **Keep-alive**: The JS client periodically pings the server to keep proxies alive in the session.
3. **Actions**: When JS calls `Glue.model.task.save()`, a POST request is sent to `/__dg__/action/task/save/`. The server reconstructs the proxy from session data, validates permissions, executes the action, and returns the result.
4. **Expiration**: If the keep-alive stops (e.g., user closes the tab), `DjangoGlueMiddleware` purges expired proxies on the next request.

## Next Steps

- Follow the [Quick Start Tutorial](quick_start.md) for a hands-on walkthrough
- Read the individual proxy guides for in-depth coverage:
  - [Model Proxy](model_object_glue.md)
  - [QuerySet Proxy](query_set_glue.md)
  - [Form Proxy](form_glue.md)
  - [Template Proxy](template_glue.md)
  - [Function Proxy](function_glue.md)
  - [GlueView](view_glue/view_glue.md)
- Explore the [Advanced Topics](advanced/access_control.md) section for access control, events, field filtering, and configuration
