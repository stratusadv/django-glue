<p align="center">
    <a href="https://django-glue.stratusadv.com">
        <img alt="Django Glue Logo" src="https://django-glue.stratusadv.com/static/img/django_glue_logo_256.png"/>
    </a>
</p>

# Django Glue

![Build](https://img.shields.io/github/actions/workflow/status/stratusadv/django-glue/run_tests.yml)
![Python Versions](https://img.shields.io/pypi/pyversions/django-glue)
![PyPI Version](https://img.shields.io/pypi/v/django-glue)
![Downloads](https://img.shields.io/pypi/dm/django-glue)

### Seamlessly Connect Django to your Frontend.

## Features

- **Proxy Pattern Architecture**
  - Transparently bind Django models, querysets, and forms to JavaScript objects.
  - Access model fields as native properties with automatic change tracking.
  - Built-in lazy loading fetches data on first access.

- **Simple, Declarative API**
  - Register proxies in your Django views with `Glue.model()`, `Glue.queryset()`, and `Glue.form()`.
  - Access proxies on the frontend as properties of the global `Glue` object (e.g., `Glue.task`, `Glue.tasks`).

- **Unintrusive Integration**
  - Works with your existing Django views and templates with minimal setup.
  - No need to rewrite your application to adopt Django Glue.

- **Frontend Framework Agnostic**
  - Designed to work with any frontend style or framework.
  - No required JavaScript dependencies beyond the included client library.

- **Granular Access Control**
  - Secure per-proxy permission levels: `VIEW`, `CHANGE`, and `DELETE`.
  - Permissions cascade — `DELETE` includes `CHANGE`, which includes `VIEW`.
  - All access checks enforced server-side on every action request.

- **Rich QuerySet Support**
  - Items returned from querysets are full model proxies with their own `save()` and `delete()`.
  - Chainable query building with `filter()`, `orderBy()`, and `slice()`.
  - Automatic parent refresh when child items are modified or deleted.

- **Form Proxy Support**
  - Bind Django Forms and ModelForms to JavaScript with full validation.
  - Automatic FormData handling for file uploads.
  - Per-field error tracking with `hasErrors()` helper.

- **Event Listener System**
  - Attach `before`, `after`, and `error` listeners to any proxy action.
  - Chainable listener management for reactive UI patterns.

- **Server-Side HTML Rendering**
  - Use `GlueView` to dynamically render HTML fragments from Django views.
  - New proxies registered during rendering are automatically initialized on the client.
