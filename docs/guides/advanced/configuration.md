# Configuration

## Overview

Django Glue provides configuration options through Django settings. The server publishes client configuration in the Glue manifest rendered by `{% django_glue_init %}`.

## Backend Configuration

All settings are defined in your Django `settings.py`. Any constant from `django_glue.settings` can be overridden by defining the same name in your project's settings.

### Proxy Policy Max Age

```python
# Signed proxy policy max age in seconds (default: 600)
DJANGO_GLUE_PROXY_POLICY_MAX_AGE_SECONDS = 600
```

Each registered proxy policy is signed with a creation timestamp. On every subsequent proxy request, Django Glue verifies the policy signature and rejects policies older than this max age.

### Request Timeout

```python
DJANGO_GLUE_REQUEST_TIMEOUT_SECONDS = 30
```

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
| `/__dg__/callable_attribute/<object_name>/` | Execute a Glue attribute request |
| `/__dg__/glue_view/` | Execute a Django view for HTML rendering |

These are sent to the client in the Glue manifest. You do not need to reference them manually.
