# Configuration

## Overview

Django Glue provides configuration options on both the backend through Django settings and the frontend through the JavaScript `GlueConfig` class.

## Backend Configuration

All settings are defined in your Django `settings.py`. Any constant from `django_glue.settings` can be overridden by defining the same name in your project's settings.

### Proxy Policy Max Age

```python
# Signed proxy policy max age in seconds (default: 600)
DJANGO_GLUE_PROXY_POLICY_MAX_AGE_SECONDS = 600
```

Each registered proxy policy is signed with a creation timestamp. On every subsequent proxy request, Django Glue verifies the policy signature and rejects policies older than this max age.

## Frontend Configuration

The JavaScript client is configured through the `{% django_glue_init %}` template tag. The configuration options are defined in the `GlueConfig` class:

| Option | Default | Description |
|--------|---------|-------------|
| `requestTimeoutSeconds` | `30` | HTTP request timeout in seconds |

## Request Timeout

All HTTP requests from the JS client respect the configured timeout. If a request exceeds the timeout, it is aborted and an error is thrown:

```javascript
try {
    await Glue.model.task.save()
} catch (error) {
    console.error('Request failed:', error)
}
```

## CSRF Protection

All POST requests from the JavaScript client include the CSRF token via the `X-CSRFToken` header. The client reads the token from `document.cookie` automatically. No additional configuration is needed.

## URL Configuration

The `{% django_glue_init %}` template tag injects the correct URL paths for the internal endpoints. The URLs are:

| Endpoint | Purpose |
|----------|---------|
| `/__dg__/bound_attribute_event/<proxy_name>/<attribute_name>/` | Execute a bound proxy attribute |
| `/__dg__/glue_view/` | Execute a Django view for HTML rendering |

These are automatically configured by the template tag. You do not need to reference them manually.
