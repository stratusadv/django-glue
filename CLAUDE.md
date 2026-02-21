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
│   │   ├── mixins.py         # Field filtering mixin
│   │   ├── model/proxy.py    # GlueModelProxy
│   │   └── queryset/proxy.py # GlueQuerySetProxy
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
│           └── queryset.js   # GlueQuerySetProxy
├── tests/                    # Test suite
│   └── test_exceptions.py    # Exception tests
├── eval/                     # Project evaluations
├── test_project/             # Django test application
└── docs/                     # MkDocs documentation
```

## Core Concepts

### The Proxy Pattern

Django Glue creates proxy objects that act as transparent interfaces between Django models/querysets and JavaScript. Each proxy:

1. Has a **unique name** identifying it in the session
2. Wraps a **target** (Model instance or QuerySet)
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

## Usage

### Backend (Django View)

```python
from django_glue import Glue, GlueAccess
from myapp.models import Task

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
const allTasks = await Glue.tasks.all()
const filtered = await Glue.tasks.filter({
    'done': false,
    'title__icontains': 'urgent'
})

// Each item is a full GlueModelProxy
filtered[0].done = true
await filtered[0].save()
```

## Key Files

| File | Purpose |
|------|---------|
| `django_glue/proxies/proxy.py` | BaseGlueProxy - core abstraction |
| `django_glue/proxies/model/proxy.py` | Model instance binding |
| `django_glue/proxies/queryset/proxy.py` | QuerySet binding |
| `django_glue/session.py` | Session proxy management & expiration |
| `django_glue/shortcuts.py` | `Glue.model()` and `Glue.queryset()` API |
| `django_glue/views.py` | HTTP endpoints for actions |
| `django_glue/exceptions.py` | Custom exceptions for error handling |
| `client_js/src/client.js` | JavaScript GlueClient singleton |
| `client_js/src/proxies/model.js` | JS model proxy with field getters/setters |
| `client_js/src/proxies/queryset.js` | JS queryset proxy with filter/all |
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
cd test_project
python manage.py runserver
```

### Testing

- **Python**: Django TestCase
- **JavaScript**: Jest
- **E2E**: Playwright

```bash
# Run Django tests
python manage.py test

# Run Playwright tests
playwright test
```

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

## Planned Features

- **Form Integration**: Django Forms binding to frontend

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
