# Installation

Django Glue requires Python 3.11 or newer and Django 5 or newer.

```bash
pip install django-glue
```

Add the app and put its response middleware last:

```python
INSTALLED_APPS = [
    # Your apps...
    'django_glue',
]

MIDDLEWARE = [
    # Your existing middleware...
    'django_glue.middleware.GlueViewMiddleware',
]
```

The last position is required because `Glue.view(url)` asks a real Django
route for an HTML envelope after the ordinary middleware chain has run.
Django's system check reports `django_glue.E002` if the position is wrong.

Include the attribute-call endpoint in the project URL configuration:

```python
from django_glue import django_glue_urls

urlpatterns = [
    # Your routes...
    *django_glue_urls(),
]
```

It registers `POST /__dg__/callable_attribute/`. `Glue.view(url)` uses the
target URL directly.

In the base template, load and render the initialization tag once:

```django
{% load django_glue %}
<!doctype html>
<html>
<head><title>My page</title></head>
<body>
    {% block content %}{% endblock %}
    {% django_glue_init %}
</body>
</html>
```

The tag emits the page's addressed objects and loads the bundled JavaScript
client. The bundle includes Alpine.js and its morph plugin. Remove separate
Alpine core and morph scripts and application calls to `Alpine.start()`.
Optional plugins may still register before Glue starts Alpine. Code that
needs mounted DOM state should use `alpine:initialized` or `$nextTick`.

The default signed policy lifetime is 24 hours from issuance. Configure
`DJANGO_GLUE_PROXY_POLICY_MAX_AGE_SECONDS` in Django settings if the
application needs another lifetime; an expired page root requires a reload.

Continue with the [quick start](../guides/quick_start.md).
