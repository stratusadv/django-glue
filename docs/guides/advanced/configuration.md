# Configuration

## Overview

Django Glue provides several configuration options on both the backend (Django settings) and the frontend (JavaScript config).

## Backend Configuration

All settings are defined in your Django `settings.py`. Any constant from `django_glue.settings` can be overridden by defining the same name in your project's settings.

### Keep-Alive Interval

```python
# Keep-alive interval in seconds (default: 600)
DJANGO_GLUE_KEEP_LIVE_INTERVAL_TIME_SECONDS = 600
```

The JS client sends keep-alive requests at this interval to keep proxies alive in the session. An additional 60-second buffer is added server-side to account for request processing time.

### Session Expiry Message

```python
# Message shown when keep-alive fails (default shown below)
DJANGO_GLUE_SESSION_EXPIRY_MESSAGE = 'Session expired. Do you want to reload the page?'
```

This message is displayed in a `confirm()` dialog when the keep-alive request fails. If the user confirms, the page reloads.

## Frontend Configuration

The JavaScript client is configured through the `{% django_glue_init %}` template tag, which passes server-side settings automatically. The configuration options are defined in the `GlueConfig` class:

### Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `requestTimeoutSeconds` | `30` | HTTP request timeout in seconds |
| `sessionExpiryMessage` | From Django settings | Message shown on keep-alive failure |
| `keepLiveIntervalSeconds` | `600` | Keep-alive polling interval in seconds |
| `minimumKeepLiveIntervalSeconds` | `120` | Hard minimum for keep-alive interval |

### Request Timeout

All HTTP requests from the JS client respect the configured timeout. If a request exceeds the timeout, it is aborted and an error is thrown:

```javascript
try {
    await Glue.model.task.save()
} catch (error) {
    // Request timed out
    console.error('Request failed:', error)
}
```

## Keep-Alive Behavior

### How It Works

1. When `Glue.init()` is called, the client starts a `setInterval` timer
2. At each interval, it collects all registered proxy names and sends them to `/__dg__/keep_live/`
3. The server updates the expiration timestamps for those proxies
4. If the keep-alive request fails, the client shows a `confirm()` dialog with the session expiry message
5. If the user confirms, the page reloads

### Minimum Interval

The JavaScript client enforces a minimum keep-alive interval of 120 seconds. Even if you configure a lower value, the client will use 120 seconds.

### Middleware Cleanup

The `DjangoGlueMiddleware` purges expired proxies on every non-glue request. This ensures that proxies from closed tabs don't accumulate in the session indefinitely.

## CSRF Protection

All POST requests from the JavaScript client include the CSRF token via the `X-CSRFToken` header. The client reads the token from `document.cookie` automatically. No additional configuration is needed.

## URL Configuration

The `{% django_glue_init %}` template tag injects the correct URL paths for the internal endpoints. The URLs are:

| Endpoint | Purpose |
|----------|---------|
| `/__dg__/action/<unique_name>/<action>/` | Execute a proxy action |
| `/__dg__/keep_live/` | Renew proxy expiration |
| `/__dg__/session_data/` | Get proxy registry |
| `/__dg__/glue_view/` | Execute a Django view for HTML rendering |

These are automatically configured by the template tag — you don't need to reference them manually.
