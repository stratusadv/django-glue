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

## Add URL Patterns

Include the Django Glue URL patterns in your project's `urls.py`:

```python
from django.urls import path, include
from django_glue import django_glue_urls

urlpatterns = [
    # ...
]

url_patterns += django_glue_urls()
```

This registers the internal endpoints under the `__dg__` namespace:

- `/__dg__/callable_attribute/<object_name>/` — Execute a Glue attribute request
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
3. The Glue manifest as JSON
4. Initialization code that creates the global `Glue` object

The client bundles Alpine.js and its morph plugin (both pinned to 3.15.12).
No separate Alpine installation is needed. Glue exposes `window.Alpine`
immediately and starts it once the document and deferred scripts are ready.
Inline Glue setup works immediately; `x-data` components mount at startup.

### Migrating an existing Alpine page

Remove separate Alpine core and morph script tags, including tags in inherited
base templates and individual widgets. Remove application calls to
`Alpine.start()`; Glue owns startup. Two Alpine runtimes on one page are not
supported.

Keep optional plugins such as intersect, mask, collapse, persist, focus, and
sort. Load their CDN scripts with `defer` and use versions compatible with the
bundled Alpine version. Register custom stores, components, and directives in
`alpine:init`, as before:

```html
<script>
    document.addEventListener('alpine:init', () => {
        Alpine.store('theme', {name: 'dark'})
    })
</script>
```

This follows Alpine's [extension registration lifecycle](https://alpinejs.dev/essentials/installation).
Avoid `async` plugin scripts, which may arrive after Alpine starts. Code that
needs initialized DOM state should use `alpine:initialized` or `$nextTick`.

For Stratus Portal, the Alpine core and six optional plugin tags come from
Spire's inherited `django_spire/base/base.html`. Remove the core tag there and
keep the six plugin tags. Spire's JSON-tree widget also has its own core script
tag that must be removed. Portal's `alpine:init` stores and inline
`Glue.onMessage` setup fit the bundled lifecycle. This is a migration checklist,
not a claim that the portal has been migrated or browser-tested.

## Optional Configuration

Override defaults in your `settings.py`:

```python
# Signed policy max age in seconds (default: 600)
DJANGO_GLUE_PROXY_POLICY_MAX_AGE_SECONDS = 600
```

## Verify Installation

After installation, you should have access to the global `Glue` object in your browser console:

```javascript
console.log(window.Glue)  // GlueClient instance
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
        exclude=['internal_notes'],  # Expose all fields except internal_notes
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
