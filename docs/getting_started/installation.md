# Installation

## Prerequisites

- Python >= 3.11
- Django >= 5

## Install the Package

```bash
pip install django-glue
```

## Add to Installed Apps

Add `django_glue` to your `INSTALLED_APPS` in `settings.py`:

```python
INSTALLED_APPS = [
    # ...
    'django_glue',
]
```

## Add Middleware

Add the `DjangoGlueMiddleware` to your `MIDDLEWARE` setting. It should be placed after Django's session middleware:

```python
MIDDLEWARE = [
    # ...
    'django.contrib.sessions.middleware.SessionMiddleware',
    # ...
    'django_glue.middleware.DjangoGlueMiddleware',
]
```

## Add URL Patterns

Include the Django Glue URL patterns in your project's `urls.py`:

```python
from django.urls import path, include
from django_glue import django_glue_urls

urlpatterns = [
    # ...
    path('', include(django_glue_urls())),
]
```

This registers the internal endpoints under the `__dg__` namespace:
- `/__dg__/bound_attribute_event/<proxy_name>/<attribute_name>/` — Execute a bound proxy attribute
- `/__dg__/glue_view/` — Execute a Django view for HTML rendering

## Add Template Tag

In your base template, load the template tags and add `{% django_glue_init %}` just before the closing `</body>` tag:

```html
{% load django_glue %}

<!DOCTYPE html>
<html lang="en">
<head>
    <title>My Page</title>
</head>
<body>
    <!-- Your page content -->

    {% django_glue_init %}
</body>
</html>
```

The `{% django_glue_init %}` tag injects:
1. The CSRF token
2. The JavaScript client library
3. Proxy registry and context data as JSON
4. Initialization code that creates the global `Glue` object

## Optional Configuration

Override defaults in your `settings.py`:

```python
# Signed proxy policy max age in seconds (default: 600)
DJANGO_GLUE_PROXY_POLICY_MAX_AGE_SECONDS = 600
```

## Verify Installation

After installation, you should have access to the global `Glue` object in your browser console:

```javascript
console.log(window.Glue)  // GlueClient instance
console.log(window.GlueConfig)  // GlueConfig class
```

## Quick Example

Here's a minimal working example:

**views.py**
```python
from django.shortcuts import render
from django_glue import Glue, GlueAccess
from myapp.models import Task

def my_view(request):
    task = Task.objects.first()

    Glue.model(
        request=request,
        unique_name='task',
        target=task,
        access=GlueAccess.CHANGE,
    )

    return render(request, 'my_template.html')
```

**my_template.html**
```html
{% load django_glue %}
<!DOCTYPE html>
<html>
<head>
    <title>Task</title>
</head>
<body>
    <script>
        Glue.model.task.get().then(() => {
            console.log('Task title:', Glue.model.task.title)
            Glue.model.task.title = 'Updated Title'
            Glue.model.task.save()
        })
    </script>

    {% django_glue_init %}
</body>
</html>
```
