# Django Glue

A library that seamlessly binds Django backend models to frontend JavaScript using the Proxy pattern.

## Quick Reference

| Item | Value |
|------|-------|
| Python | >= 3.11 |
| Django | >= 5 |
| License | MIT |
| Docs | https://django-glue.stratusadv.com |
| Repo | https://github.com/stratusadv/django-glue |

## Project Structure

```
django-glue/
├── django_glue/              # Main Python package
│   ├── proxies/              # Proxy pattern implementation
│   │   ├── proxy.py          # BaseGlueProxy abstract base class
│   │   ├── decorators.py     # @action decorator
│   │   ├── fields/           # Field validation system
│   │   │   ├── mixin.py      # GlueProxyModelFieldsMixin
│   │   │   └── validators.py # Type validators
│   │   ├── model/proxy.py    # GlueModelProxy
│   │   ├── queryset/proxy.py # GlueQuerySetProxy
│   │   └── form/proxy.py     # GlueFormProxy
│   ├── access/               # Permission system
│   │   └── access.py         # GlueAccess enum (VIEW, CHANGE, DELETE)
│   ├── exceptions.py         # Custom exceptions (GlueError, etc.)
│   ├── session.py            # Session-based proxy management
│   ├── views.py              # Django views (action, keep_live)
│   ├── shortcuts.py          # Glue class - main API entry point
│   ├── middleware.py         # Proxy cleanup middleware
│   ├── context_processors.py # Template context provider
│   └── templatetags/         # {% django_glue_init %} tag
├── client_js/                # JavaScript client source
│   ├── glue.js               # Entry point
│   └── src/
│       ├── client.js         # GlueClient class
│       ├── config.js         # Global configuration
│       ├── http.js           # HTTP utilities (with timeout support)
│       └── proxies/          # JS proxy implementations
│           ├── base.js       # BaseGlueProxy
│           ├── model.js      # GlueModelProxy
│           ├── queryset.js   # GlueQuerySetProxy
│           └── form.js       # GlueFormProxy
├── tests/                    # Test suite
│   ├── test_exceptions.py    # Exception tests
│   ├── proxies/              # Proxy tests
│   │   ├── fields/           # Field validation tests
│   │   ├── model/            # Model proxy tests
│   │   └── queryset/         # QuerySet proxy tests
│   └── session/              # Session tests
├── eval/                     # Project evaluations
├── test_project/             # Django test application
└── docs/                     # MkDocs documentation
```

## Core Concepts

### The Proxy Pattern

Django Glue creates proxy objects that act as transparent interfaces between Django models/querysets/forms and JavaScript. Each proxy:

1. Has a **unique name** identifying it in the session
2. Wraps a **target** (Model instance, QuerySet, or Form)
3. Has an **access level** (VIEW, CHANGE, or DELETE)
4. Exposes **actions** callable from JavaScript

### Access Control

```python
from django_glue import GlueAccess

# Permission cascade (higher includes lower):
# DELETE > CHANGE > VIEW

GlueAccess.VIEW    # Read-only
GlueAccess.CHANGE  # Read + write (includes VIEW)
GlueAccess.DELETE  # Read + write + delete (includes CHANGE)
```

### The @action Decorator

Marks proxy methods as callable from JavaScript. The built-in proxies use this internally:

- `GlueModelProxy`: `get()`, `save()`, `delete()`
- `GlueQuerySetProxy`: `all()`, `filter()`, `save()`, `delete()`
- `GlueFormProxy`: `get()`, `validate()`, `submit()`

### Payload Validation

Model and QuerySet proxies validate incoming data using Django's `modelform_factory`. This provides:

- Full Django form validation (max_length, min_value, max_value, etc.)
- Custom field validators
- Type coercion (e.g., string "42" → integer 42)
- Field filtering (only included fields are validated/saved)

## Usage

### Backend (Django View)

```python
from django_glue import Glue, GlueAccess
from myapp.models import Task
from myapp.forms import TaskForm, ContactForm

def my_view(request):
    # Register a single model instance
    Glue.model(
        request=request,
        unique_name='task',
        target=Task.objects.first(),
        access=GlueAccess.DELETE,
    )

    # Register a queryset
    Glue.queryset(
        request=request,
        unique_name='tasks',
        target=Task.objects.all(),
        access=GlueAccess.CHANGE,
        fields=['id', 'title', 'done'],  # Optional field filtering
    )

    # Register a form (ModelForm or regular Form)
    Glue.form(
        request=request,
        unique_name='task_form',
        target=TaskForm(instance=task),
        access=GlueAccess.CHANGE,
    )

    Glue.form(
        request=request,
        unique_name='contact_form',
        target=ContactForm(),
        access=GlueAccess.CHANGE,
    )

    return render(request, 'page.html')
```

### Template

```html
{% load django_glue %}
<!DOCTYPE html>
<html>
<head>
    {% django_glue_init %}
</head>
<body>
    <!-- Your frontend code -->
</body>
</html>
```

### Frontend (JavaScript)

```javascript
// Model proxy - access fields directly
const title = Glue.task.title       // Auto-fetches if needed
Glue.task.title = 'New Title'       // Updates internal state
await Glue.task.save()              // Persists to Django
await Glue.task.delete()            // Deletes instance

// QuerySet proxy - work with collections
const allTasks = await Glue.tasks.queryWithParams()
const filtered = await Glue.tasks.filter({
    'done': false,
    'title__icontains': 'urgent'
})

// Each item is a full GlueModelProxy
filtered[0].done = true
await filtered[0].save()

// Form proxy - validation and submission
Glue.contact_form.name = 'John'
Glue.contact_form.email = 'john@example.com'

// Validate without saving
const validation = await Glue.contact_form.validate(Glue.contact_form.values)
if (validation.is_valid) {
    // Submit (saves for ModelForm, returns cleaned_data for regular Form)
    const result = await Glue.contact_form.submit(Glue.contact_form.values)
    if (result.success) {
        console.log('Submitted:', result.data)
    } else {
        console.log('Errors:', result.errors)
    }
}
```

## Key Files

| File | Purpose |
|------|---------|
| `django_glue/proxies/proxy.py` | BaseGlueProxy - core abstraction |
| `django_glue/proxies/model/proxy.py` | Model instance binding |
| `django_glue/proxies/queryset/proxy.py` | QuerySet binding |
| `django_glue/proxies/form/proxy.py` | Form binding with validation |
| `django_glue/proxies/fields/mixin.py` | GlueProxyModelFieldsMixin for field filtering & validation |
| `django_glue/session.py` | Session proxy management & expiration |
| `django_glue/shortcuts.py` | `Glue.model()`, `Glue.queryset()`, `Glue.form()` API |
| `django_glue/views.py` | HTTP endpoints for actions |
| `django_glue/exceptions.py` | Custom exceptions for error handling |
| `client_js/src/client.js` | JavaScript GlueClient singleton |
| `client_js/src/proxies/model.js` | JS model proxy with field getters/setters |
| `client_js/src/proxies/queryset.js` | JS queryset proxy with filter/all |
| `client_js/src/proxies/form.js` | JS form proxy with validation |
| `client_js/src/config.js` | Global JS client configuration |

## Exceptions

Custom exceptions in `django_glue/exceptions.py`:

| Exception | When Raised |
|-----------|-------------|
| `GlueError` | Base exception for all Glue errors |
| `GlueProxyNotFoundError` | Proxy not found in session |
| `GlueAccessError` | Insufficient permissions for action |
| `GlueMissingActionError` | Action method doesn't exist |
| `GlueModelInstanceNotFoundError` | Model instance not found (DoesNotExist) |
| `GlueQuerySetFilterValidationError` | Filter references disallowed field |
| `GluePayloadValidationError` | Field validation failed (type, max_length, etc.) |

## Development

### Setup

```bash
# Install Python dependencies
pip install -e ".[development]"

# Install Node dependencies (for JS client)
npm install
```

### Building JavaScript Client

```bash
# Build once
npm run build

# Watch mode (rebuilds on changes)
npm run watch
```

Output goes to `django_glue/static/django_glue/js/glue.js` and `glue.min.js`.

### Running the Test Project

```bash
DJANGO_SETTINGS_MODULE=test_project.base_settings python manage.py runserver
```

### Testing

- **Python**: pytest with pytest-django
- **JavaScript**: Jest with Babel
- **E2E**: Playwright

```bash
# Run Python tests
python -m pytest tests/ -v

# Run JavaScript tests
npm test

# Run Playwright tests
playwright test
```

#### Why Babel for Jest?

The JavaScript source uses ES modules (`import`/`export`), but Jest runs in Node.js which defaults to CommonJS. Babel transpiles ES modules to CommonJS so Jest can execute the tests. We evaluated esbuild-based alternatives (`esbuild-jest`, `@jgoz/jest-esbuild`) but found them to be niche packages with modest adoption. Babel + Jest is the mainstream, battle-tested approach with broad community support.

#### Why jest-environment-jsdom?

The JavaScript client uses browser APIs (`document.cookie` for CSRF tokens, `window.location.reload()` for session expiry, `fetch` for HTTP requests). Jest's default Node environment doesn't provide these globals. `jest-environment-jsdom` provides a simulated browser environment via JSDOM, allowing tests to access `document`, `window`, and other browser APIs without manual mocking. This is the standard approach used by Create React App, Vue CLI, and most browser-oriented JavaScript testing.

## Session Management

Proxies are stored in Django sessions with automatic expiration:

- **Keep-alive interval**: 120 seconds (configurable)
- **Client polling**: JS client sends keep-alive requests automatically
- **Middleware cleanup**: `DjangoGlueMiddleware` purges expired proxies

Settings (in Django settings.py):
```python
DJANGO_GLUE_KEEP_LIVE_INTERVAL_TIME_SECONDS = 120
```

## Request/Response Flow

1. **JS calls action** (e.g., `Glue.task.save()`)
2. **HTTP POST** to `/django_glue/` with:
   ```json
   {
     "unique_name": "task",
     "action": "save",
     "payload": {"title": "...", ...}
   }
   ```
3. **Django view** retrieves proxy from session
4. **Access check** against required permission
5. **Action executes** on the Django model
6. **Response** with result data

## JavaScript Configuration

The JS client supports global configuration during init:

```javascript
Glue.init({
    proxyRegistryFromSession: ...,
    contextDataForProxies: ...,
    keepLiveInterval: ...,
    config: {
        requestTimeoutMs: 30000  // Default: 30 seconds
    }
})
```

## Coding Standards

- Python: PEP 8 / Django conventions
- JavaScript: Mirrors Python patterns for familiarity

## URLs

Include in your Django urls.py:
```python
from django_glue.shortcuts import django_glue_urls

urlpatterns = [
    path('', include(django_glue_urls())),
    # ...
]
```

Endpoints:
- `POST /django_glue/` - Execute proxy actions
- `POST /django_glue/keep_live/` - Renew session proxies
- `GET /django_glue/session_data/` - Get current proxy registry
