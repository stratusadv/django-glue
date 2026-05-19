# Django Glue

A library that seamlessly binds Django backend models to frontend JavaScript using the Proxy pattern.

## Quick Reference

| Item | Value |
|------|-------|
| Python | >= 3.11 |
| Django | >= 5 |
| JS Runtime | Bun |
| License | MIT |
| Version | 1.0.0a1 |
| Docs | https://django-glue.stratusadv.com |
| Repo | https://github.com/stratusadv/django-glue |

## Project Structure

```
django-glue/
├── django_glue/                      # Main Python package
│   ├── __init__.py                   # Exports: Glue, django_glue_urls, GlueAccess
│   ├── constants.py                  # String constants, version, session keys
│   ├── settings.py                   # Default settings (keep-alive interval, etc.)
│   ├── conf.py                       # Settings loader with Django settings override
│   ├── maps.py                       # SUBJECT_TYPE_TO_PROXY_TYPE map
│   ├── encoders.py                   # GlueActionDataJSONEncoder
│   ├── utils.py                      # Helpers: queryset serialization, class import
│   ├── data_transfer_objects.py      # GlueActionRequestData (Pydantic)
│   │
│   ├── proxies/                      # Proxy pattern implementation
│   │   ├── proxy.py                  # BaseGlueProxy abstract base class
│   │   ├── decorators.py             # @action decorator
│   │   ├── session_data.py           # GlueSessionData dataclass
│   │   ├── model/
│   │   │   ├── base.py               # GlueModelProxyBase (abstract, combines mixins)
│   │   │   └── proxy.py              # GlueModelProxy (single model instance)
│   │   ├── queryset/
│   │   │   └── proxy.py              # GlueQuerySetProxy (queryset collection)
│   │   └── form/
│   │       ├── mixin.py              # GlueFormProxyMixin (validation, save actions)
│   │       └── proxy.py              # GlueFormProxy (Django Form binding)
│   │
│   ├── access/                       # Permission system
│   │   ├── access.py                 # GlueAccess enum (VIEW, CHANGE, DELETE)
│   │   ├── actions.py                # BaseAction (dead code)
│   │   └── decorators.py             # check_access (dead code, broken import)
│   │
│   ├── exceptions.py                 # Custom exceptions (GlueError, etc.)
│   ├── session.py                    # GlueSession - proxy registration & expiration
│   ├── views.py                      # HTTP endpoints (action, keep_live, glue_view)
│   ├── shortcuts.py                  # Glue class - main API entry point
│   ├── middleware.py                 # DjangoGlueMiddleware - expired proxy cleanup
│   ├── urls.py                       # URL patterns (namespace: __dg__)
│   └── templatetags/
│       ├── django_glue.py            # {% django_glue_init %} inclusion tag
│       └── utils.py                  # get_item template filter
│
├── client_js/                        # JavaScript client source
│   ├── django_glue.js                # Entry point - creates singleton, exposes globals
│   ├── scripts/
│   │   └── build.js                  # Bun bundler script
│   ├── src/
│   │   ├── client.js                 # GlueClient class - init, keep-alive, proxy creation
│   │   ├── config.js                 # GlueConfig class - configuration defaults
│   │   ├── http.js                   # GlueHttp - fetch wrapper, CSRF, timeout
│   │   ├── utils.js                  # snakeToPascal utility
│   │   ├── view.js                   # GlueView - server-side HTML rendering
│   │   └── proxies/
│   │       ├── index.js              # SUBJECT_TYPE_TO_PROXY_CLASS, window globals
│   │       ├── base.js               # BaseGlueProxy - listeners, _processAction
│   │       ├── form.js               # GlueFormProxy - field accessors, validation
│   │       ├── model.js              # GlueModelProxy - get, delete, _isNew
│   │       └── queryset.js           # GlueQuerySetProxy - filter, child proxies
│   └── tests/
│       ├── setup.js                  # Happy-dom global registration
│       ├── testUtils.js              # Mock fetch, cookie, context data helpers
│       ├── client.test.js            # GlueClient tests
│       ├── config.test.js            # Config tests
│       ├── http.test.js              # HTTP tests
│       └── proxies/                  # Proxy tests (base, form, model, queryset)
│
├── test_project/                     # Django test application
│   ├── settings.py                   # Test settings (SQLite, DEBUG)
│   ├── urls.py                       # Test URL routing
│   ├── test_forms.py                 # ContactForm, TestModelForm
│   ├── gorilla/                      # Primary test app (Gorilla, Skill models)
│   ├── fight/                        # Secondary test app
│   ├── comments/                     # Secondary test app
│   ├── lab/                          # Views and URLs only
│   └── core/                         # Custom template tags
│
├── django_glue/tests/                # Python test suite
│   ├── conftest.py                   # Pytest config, fixtures
│   ├── test_exceptions.py            # Exception class tests
│   ├── access/test_access.py         # GlueAccess hierarchy tests
│   ├── session/test_session.py       # Session management tests
│   ├── proxies/
│   │   ├── fields/test_mixin_validation.py  # Payload validation tests
│   │   ├── model/actions/            # Model proxy action tests
│   │   ├── queryset/actions/         # QuerySet proxy action tests
│   │   └── form/                     # Form proxy tests
│   │       ├── test_form_proxy.py
│   │       └── actions/              # Form action tests
│
└── docs/                             # MkDocs documentation
    ├── api/                          # API reference docs
    ├── guides/                       # Usage guides
    ├── getting_started/              # Installation guide
    ├── changelog/                    # Version changelog
    └── roadmap/                      # Future plans
```

## Core Concepts

### The Proxy Pattern

Django Glue creates proxy objects that act as transparent interfaces between Django models/querysets/forms and JavaScript. Each proxy:

1. Has a **unique name** identifying it in the session
2. Wraps a **target** (Model instance, QuerySet, or Form)
3. Has an **access level** (VIEW, CHANGE, or DELETE)
4. Exposes **actions** callable from JavaScript

### Proxy Class Hierarchy (Python)

```
ABC
  └── BaseGlueProxy (proxies/proxy.py)
        └── GlueFormProxyMixin (proxies/form/mixin.py)
              ├── GlueModelProxyBase (proxies/model/base.py)
              │     ├── GlueModelProxy (proxies/model/proxy.py)
              │     └── GlueQuerySetProxy (proxies/queryset/proxy.py)
              └── GlueFormProxy (proxies/form/proxy.py)
```

### Proxy Class Hierarchy (JavaScript)

```
BaseGlueProxy
    ├── GlueFormProxy
    │     └── GlueModelProxy
    └── GlueQuerySetProxy
```

### Access Control

```python
from django_glue import GlueAccess

# Permission cascade (higher includes lower):
# DELETE > CHANGE > VIEW

GlueAccess.VIEW    # Read-only
GlueAccess.CHANGE  # Read + write (includes VIEW)
GlueAccess.DELETE  # Read + write + delete (includes CHANGE)
```

`GlueAccess` inherits from both `str` and `Enum`, serializing cleanly to JSON as `'view'`, `'change'`, `'delete'`. The `has_access()` method compares enum member indices to enforce the cascade.

### The @action Decorator

Defined in `proxies/decorators.py`. Marks proxy methods as callable from JavaScript:

```python
@action(GlueAccess.VIEW)
def get(self, action_data):
    ...
```

The `@action` decorator sets `_required_glue_access` on the wrapped function. `BaseGlueProxy.__init_subclass__` auto-discovers methods with this attribute and registers them in the class-level `_actions` dict, extracting method parameters and type annotations.

**Convention**: All action methods accept exactly one parameter: `action_data: GlueActionRequestData`.

### Built-in Actions by Proxy Type

| Proxy | Actions | Required Access |
|-------|---------|-----------------|
| `GlueModelProxy` | `get()`, `save()`, `delete()`, `validate()`, `foreign_key_choices()` | VIEW, CHANGE, DELETE |
| `GlueQuerySetProxy` | `query_with_params()`, `save()`, `delete()`, `get()`, `new()` | VIEW, CHANGE, DELETE |
| `GlueFormProxy` | `get()`, `validate()`, `save()`, `foreign_key_choices()` | VIEW, CHANGE |

### Payload Validation

Model and QuerySet proxies validate incoming data using Django's `modelform_factory`. This provides:
- Full Django form validation (max_length, min_value, max_value, etc.)
- Custom field validators
- Type coercion (e.g., string "42" → integer 42)
- Field filtering (only included fields are validated/saved)

The save pipeline in `GlueModelProxyBase._save()`:
1. `_set_non_m2m_fields()` - sets non-M2M fields via `field.save_form_data()`
2. `model_instance.save()` - persists to database
3. `_set_m2m_fields()` - sets M2M fields (requires saved instance)

File fields are deferred until after other fields so `upload_to` callables can reference other field values.

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

    # ModelForm registers as GlueModelProxy (not GlueFormProxy)
    Glue.form(
        request=request,
        unique_name='task_form',
        target=TaskForm(instance=task),
        access=GlueAccess.CHANGE,
    )

    # Regular Form registers as GlueFormProxy
    Glue.form(
        request=request,
        unique_name='contact_form',
        target=ContactForm(),
        access=GlueAccess.CHANGE,
    )

    return render(request, 'page.html')
```

### Method-Chain Syntax

```python
Glue.request(request) \
    .model(unique_name='task', target=task, access=GlueAccess.DELETE) \
    .queryset(unique_name='tasks', target=Task.objects.all(), access=GlueAccess.CHANGE)
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

The `{% django_glue_init %}` tag renders `templates/django_glue/django_glue.html`, which injects:
1. CSRF token
2. JS script tag (version cache-busted)
3. JSON data for proxy registry and context data
4. Initialization code creating `GlueConfig` and calling `Glue.init()`

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

const validation = await Glue.contact_form.validate()
if (validation.success) {
    const result = await Glue.contact_form.save()
}
```

### GlueView - Server-Side HTML Rendering

```javascript
const view = Glue.view('/some/url/')
await view.renderInnerHtml('#target-element', { param: 'value' })
```

`GlueView` enables server-side rendering of HTML fragments with embedded Glue proxies. The server renders the target URL, registers any new proxies, and returns `{html, proxy_registry_data, proxy_context_data}`. The client calls `Glue.initializeProxies()` to register the new proxies.

## Key Files

| File | Purpose |
|------|---------|
| `django_glue/proxies/proxy.py` | BaseGlueProxy - core abstraction, action registration, request processing |
| `django_glue/proxies/model/base.py` | GlueModelProxyBase - field handling, save pipeline, form class resolution |
| `django_glue/proxies/model/proxy.py` | GlueModelProxy - single model instance binding |
| `django_glue/proxies/queryset/proxy.py` | GlueQuerySetProxy - queryset binding with serialization |
| `django_glue/proxies/form/mixin.py` | GlueFormProxyMixin - validation, save, foreign_key_choices actions |
| `django_glue/proxies/form/proxy.py` | GlueFormProxy - Django Form binding |
| `django_glue/proxies/decorators.py` | @action decorator |
| `django_glue/session.py` | GlueSession - proxy registration, expiration, renewal |
| `django_glue/shortcuts.py` | Glue class - main API entry point |
| `django_glue/views.py` | HTTP endpoints: action_view, keep_live_view, glue_view_view, session_data_view |
| `django_glue/data_transfer_objects.py` | GlueActionRequestData - Pydantic model for request parsing |
| `django_glue/encoders.py` | GlueActionDataJSONEncoder - handles Model, QuerySet, FieldFile serialization |
| `django_glue/exceptions.py` | Custom exceptions for error handling |
| `django_glue/urls.py` | URL configuration (namespace: `__dg__`) |
| `client_js/src/client.js` | GlueClient singleton - init, keep-alive, proxy creation |
| `client_js/src/http.js` | GlueHttp - fetch wrapper, CSRF, timeout, action requests |
| `client_js/src/proxies/base.js` | BaseGlueProxy - listener system, _processAction |
| `client_js/src/proxies/model.js` | GlueModelProxy - field accessors, get, delete |
| `client_js/src/proxies/queryset.js` | GlueQuerySetProxy - filter, child proxy creation |
| `client_js/src/proxies/form.js` | GlueFormProxy - field definitions, validation, FormData |
| `client_js/src/view.js` | GlueView - server-side HTML rendering |
| `client_js/src/config.js` | GlueConfig - configuration defaults |

## Session Management

### Architecture

Proxies are NOT stored in the session. Only their `unique_name` and `access` level are persisted. The proxy is reconstructed on each request from `context_data` sent by the client.

```python
request.session['django_glue_proxies'] = {
    'proxy_unique_name': GlueAccess.VIEW,
    ...
}
request.session['django_glue_keep_live'] = {
    'proxy_unique_name': 1712345678.0,  # Unix timestamp of expiration
    ...
}
```

### Key Behaviors

- **Keep-alive interval**: 600 seconds default (configurable via `DJANGO_GLUE_KEEP_LIVE_INTERVAL_TIME_SECONDS`)
- **Expiration buffer**: +60 seconds added beyond the configured interval to account for request processing time
- **Client polling**: JS client sends keep-alive requests automatically via `setInterval`
- **Middleware cleanup**: `DjangoGlueMiddleware` purges expired proxies on every non-glue request
- **Session modification**: `_set_modified()` marks session as modified (required for Django to persist changes)

### Settings (in Django settings.py)

```python
DJANGO_GLUE_KEEP_LIVE_INTERVAL_TIME_SECONDS = 600  # Default: 600
DJANGO_GLUE_SESSION_EXPIRY_MESSAGE = 'Session expired. Do you want to reload the page?'
```

Any `django_glue.settings` constant can be overridden by defining the same name in your Django project's `settings.py`. The `Settings` class in `conf.py` checks Django settings first, then falls back to defaults.

## Request/Response Flow

### Registration Flow (Page Load)

1. Django view calls `Glue.model(request, unique_name='task', target=task, access=GlueAccess.DELETE)`
2. `Glue.glue()` creates `GlueModelProxy` instance
3. `GlueSession.register_proxy()` stores `{unique_name: access}` in session + sets expiration
4. `proxy.to_context_data()` serializes proxy metadata (actions, fields, model info)
5. Context data stored on `request.__glue_context_data__['task']`
6. Template renders `{% django_glue_init %}` which injects JS with proxy registry and context data
7. JS client parses context data and creates JavaScript proxy objects

### Action Flow (JS -> Django)

1. JS calls `Glue.task.save()`
2. JS POSTs to `/__dg__/action/task/save/` with body:
   ```json
   {
     "context_data": { "subject_type": "Model", "model_class": "...", "app_label": "...", "target_pk": 1, ... },
     "post_data": { "name": "New Name", ... },
     "file_data": {}
   }
   ```
3. `action_view` parses request into `GlueActionRequestData`
4. `GlueSession.get_proxy_access('task')` retrieves access level from session
5. `SUBJECT_TYPE_TO_PROXY_TYPE['Model'].from_action_request_data(...)` reconstructs `GlueModelProxy`
6. `proxy.process_action('save', action_data)` validates access and calls the `save` method
7. Result dict returned as `JsonResponse` with `GlueActionDataJSONEncoder`

### Keep-Alive Flow

1. JS client periodically POSTs to `/__dg__/keep_live/` with `{ "unique_names": ["task", "tasks"] }`
2. `keep_live_view` calls `GlueSession.renew_proxies()` to update expiration timestamps
3. Returns current proxy registry

### Expiration Flow

1. On any non-glue request, `DjangoGlueMiddleware` calls `GlueSession.purge_expired_proxies()`
2. Expired proxies (current time > expiration timestamp) are removed from both registries
3. Session is marked modified to persist changes

## URLs

Include in your Django urls.py:
```python
from django_glue.shortcuts import django_glue_urls

urlpatterns = [
    path('', include(django_glue_urls())),
    # ...
]
```

Endpoints (namespace: `__dg__`):
| Method | Path | View | Purpose |
|--------|------|------|---------|
| POST | `/__dg__/action/<unique_name>/<action>/` | `action_view` | Execute proxy action |
| POST | `/__dg__/keep_live/` | `keep_live_view` | Renew proxy expiration |
| GET | `/__dg__/session_data/` | `session_data_view` | Get proxy registry |
| POST | `/__dg__/glue_view/` | `glue_view_view` | Execute another Django view |

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
| `GluePayloadValidationError` | Field validation failed (defined but not raised) |

Each exception stores its parameters as instance attributes for programmatic access and generates a descriptive error message.

## JavaScript Client

### Architecture

The JS client is a singleton `GlueClient` exposed as `window.Glue`. It mirrors the Python proxy system:

| Python | JavaScript |
|--------|------------|
| `BaseGlueProxy` | `BaseGlueProxy` |
| `GlueModelProxy` extends `GlueModelProxyBase` | `GlueModelProxy` extends `GlueFormProxy` |
| `GlueQuerySetProxy` extends `GlueModelProxyBase` | `GlueQuerySetProxy` extends `BaseGlueProxy` |
| `GlueFormProxy` extends mixin + `BaseGlueProxy` | `GlueFormProxy` extends `BaseGlueProxy` |
| `@action` decorator auto-registers methods | Actions come from `contextData.actions` sent from Python |
| `to_context_data()` serializes proxy state | `contextData` received and used to build proxy |
| `subject_type.__name__` in context data | `SUBJECT_TYPE_TO_PROXY_CLASS` map by string name |

### Event System

Each JS proxy supports a listener pattern with three event types: `'before'`, `'after'`, `'error'`.

```javascript
Glue.task.addListener('save', (event) => {
    console.log('Before save:', event.payload)
}, 'before')

Glue.task.addListener('save', (event) => {
    console.log('After save:', event.result)
}, 'after')
```

### Field Access

JS proxies define property getters/setters for each field. Model proxies support lazy loading - accessing a field triggers `get()` if data hasn't been loaded yet.

### Keep-Alive

The JS client starts a `setInterval` on init, collecting all proxy names and sending them to `/__dg__/keep_live/`. On failure, it shows a `confirm()` dialog with the session expiry message and reloads the page if confirmed.

## Development

### IMPORTANT: Always Use Justfile

**ALWAYS use `just` commands instead of running commands directly.** The justfile loads environment variables from `development.env` which are required for the project to function correctly.

| Task | Command |
|------|---------|
| Run Python tests | `just run-tests` |
| Run Python tests with coverage | `just run-coverage` |
| Run JS tests | `just js-tests` |
| Run JS tests in watch mode | `just js-tests-watch` |
| Build JS bundle | `just js-build` |
| Run dev server | `just run-server` |
| Migrate and seed DB | `just migrate-and-seed` |
| Run doc tests | `just run-doc-tests` |
| Lock dependencies (bun + uv) | `just lock` |
| Create venv | `just venv` |

### Testing After Changes

**ALWAYS run tests after making any code changes, before finishing a request.**

- After changing **Python code**: run `just run-tests`
- After changing **JavaScript code**: run `just js-tests`
- After changing **both**: run both commands
- If tests fail, fix the issue and re-run until all tests pass

### Setup

```bash
# Install Python dependencies
pip install -e ".[development]"

# Install Bun (https://bun.sh)
# Then install JS dependencies
bun install
```

### Building JavaScript Client

```bash
# Build once
bun run build

# Watch mode (rebuilds on changes)
bun run watch
```

Output goes to `django_glue/static/django_glue/js/django_glue.js` and `django_glue.min.js`.

The build uses Bun's native bundler (`Bun.build()`) with `target: 'browser'` and `format: 'iife'`. No webpack or babel involved.

### Running the Test Project

```bash
DJANGO_SETTINGS_MODULE=test_project.settings python manage.py runserver
```

The manage.py lives at `test_project/manage.py`.

### Testing

- **Python**: pytest with pytest-django
- **JavaScript**: Bun test with Happy-DOM

```bash
# Run Python tests
python -m pytest django_glue/tests/ -v

# Run JavaScript tests
bun test

# Run JavaScript tests with coverage
bun test --coverage
```

#### Why Bun + Happy-DOM for JS tests?

The JavaScript client uses browser APIs (`document.cookie` for CSRF tokens, `window.location.reload()` for session expiry, `fetch` for HTTP requests). Bun provides a fast runtime with native bundling and test execution. `@happy-dom/global-registrator` provides a simulated browser environment, allowing tests to access `document`, `window`, and other browser APIs without manual mocking.

### Code Quality

```bash
# Lint and format Python
ruff check .
ruff format .

# Type check Python
ty check django_glue/
# or
pyright django_glue/
```

### CI/CD

GitHub Actions workflows in `.github/workflows/`:
- **ci.yml**: Linting (Python 3.11), tests (3.11/3.12/3.13 matrix), JS tests (Bun), security
- **publish_pypi_package.yml**: Builds and publishes to PyPI on release
- **uv_lock.yml**: Auto-updates uv.lock on dependency changes

CI uses custom `stratusadv/github-actions` reusable actions and `test_project.settings` as the settings module.

## Test Conventions

### Python Tests

- All tests inherit from `django.test.TestCase`
- Test classes follow `Glue{Component}{Feature}TestCase` naming
- Test methods use `test_{action}_{condition}` naming
- Every action test verifies permission requirements with explicit `GlueAccessError` assertions
- Uses the `Gorilla` model from `test_project.gorilla.models` as the primary test model

### JavaScript Tests

- Uses `createMockFetch()` to mock HTTP responses
- Uses `setupCookieMock()` to set cookies for CSRF testing
- Uses `createMockContextData()` to build proxy context data fixtures

## Known Issues and Dead Code

| File | Issue |
|------|-------|
| `access/decorators.py` | Imports from non-existent `django_glue.response.responses`; not used anywhere |
| `access/actions.py` | `BaseAction` class references `Access` (not `GlueAccess`); not used anywhere |
| `conf.py` | Uses `raise f'...'` instead of `raise AttributeError(f'...')` |
| `proxies/session_data.py` | `GlueSessionData` dataclass defined but not used |
| `data_transfer_objects.py` | `GlueActionRequestFormData`, `GlueActionResponseData` defined but not used |
| `shortcuts.py` | `ForeignKeyField` dataclass defined but not used |
| `exceptions.py` | `GluePayloadValidationError` defined but never raised |
| JS tests | Reference non-existent APIs (public properties, methods, module exports) that don't match current source |

## Test Coverage Gaps

The following areas currently have no tests:
- **Views**: `action_view`, `keep_live_view`, `glue_view_view`, `session_data_view`
- **Middleware**: `DjangoGlueMiddleware`
- **Shortcuts**: `Glue.model()`, `Glue.queryset()`, `Glue.form()`
- **Template tags**: `{% django_glue_init %}`
- **DTOs**: `GlueActionRequestData` validation
- **Encoders**: `GlueActionDataJSONEncoder`
- **Utils**: `serialize_queryset`, `deserialize_queryset`, `get_class_from_path_string`
- **Decorators**: `@action` decorator behavior
- **Base proxy**: `BaseGlueProxy.process_request`, `process_action`
- **E2E**: No Playwright tests exist despite `playwright` being a dev dependency

## Security Notes

- QuerySet serialization uses `pickle` + `base64`. This is safe because data is stored in server-side Django sessions (signed and encrypted), never transmitted to the client.
- CSRF protection is enforced on all POST endpoints via Django's built-in middleware and the JS client's `X-CSRFToken` header injection.
- Access control is enforced server-side on every action request.
