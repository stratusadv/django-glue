# Components

A component is a Glue object with a Django template. Put its class in an
installed app's `components.py` or `components/` package; Glue discovers those
modules at startup.

```python
from django_glue import Glue


class CounterCard(Glue.Component):
    template = 'counter/card.html'

    start: int = Glue.attr(parameter=True)
    count: int = Glue.attr(0, editable=True)
    counted = Glue.event()

    def mount(self):
        self.count = self.start

    @Glue.attr
    def increment(self):
        self.count += 1
        self.counted(value=self.count)
```

`mount()` runs after parameters are assigned and the request is bound, before
the component's first policy and HTML are produced. It does not run when a
signed policy is reconstructed for a later action.

Stamp it with the ordinary Django template tag:

```django
{% load django_glue %}
{% for start in starts %}
    {% glue_component 'counter-card' start=start key=start %}
{% endfor %}
```

The first argument is the registered tag name. It defaults to the class name in
kebab case and can be set with `tag_name`. Named arguments resolve as Django
filter expressions, so `start=start` passes the Python value. Only declared
parameters are accepted. `key` is required inside a loop, must remain stable
for the same logical child, and cannot be a loop index. `access` may override
the component's default `VIEW` access. A component template must render exactly
one HTML root element; Glue adds its address marker to that root.

```django
<section>
    <button @click="component.increment()">Increment</button>
    <span x-text="component.count"></span>
</section>
```

The server template context exposes the Python component as `component`; the
mounted Alpine scope exposes its client proxy under the same name. `$glue`
resolves that proxy from an element inside the component. Outside Alpine,
`Glue.from(element)` finds the nearest component root. `component.$el` returns
its current root. Components are addressed objects and do not receive global
names under `Glue.component`.

Changing a component parameter rerenders and morphs its mounted root. Call
`component.$refresh()` when data outside that component changes, such as a
record saved by a modal. The refresh recomputes its properties and markup,
reconciles addressed children, and morphs the root. Stable child keys preserve
their proxies and Alpine state; removed roots dispose their addresses.
`render()` produces HTML for initial or host mounting.

## Use a component as a URL view

Register a component directly in Django's URL patterns with `as_view()`:

```python
from django.urls import path
from .components import CounterCard

urlpatterns = [
    path('cards/<int:start>/', CounterCard.as_view(), name='card-fragment'),
    path(
        'cards/<int:start>/page/',
        CounterCard.as_view(template='cards/page.html'),
        name='card-page',
    ),
]
```

Named URL captures supply declared component parameters. The default response
is the component's own template as an HTML fragment. A `template=` override
wraps that fragment in a page template.

For parameters or access derived from the request, override the class hook:

```python
@classmethod
def get_view_kwargs(cls, request, **url_kwargs):
    return {**url_kwargs, 'user_id': request.user.pk}
```

The returned kwargs go to the component constructor; `access` may be included
to set the request's capability ceiling. The default hook returns the URL and
`as_view()` kwargs unchanged.

The page template places the rendered component in its layout:

```django
{% extends 'base.html' %}
{% block content %}{{ component_html }}{% endblock %}
```

The page layout must load Glue with `{% django_glue_init %}`. The component
still uses its declared template for later reactive rerenders. These URLs serve
GET and HEAD; component actions use Glue's normal addressed endpoint.

Use Django's view decorators to guard the initial URL. Override `authorize()`
on the component to check permission again for later Glue calls:

```python
from django.contrib.auth.decorators import permission_required
from django_glue import Glue


class EntryPage(Glue.Component):
    template = 'entries/entry.html'

    def is_authorized(self, request, operation):
        if operation.required_access == Glue.Access.CHANGE:
            return request.user.has_perm('entries.change_entry')
        return request.user.has_perm('entries.view_entry')


urlpatterns = [
    path(
        'entries/',
        permission_required('entries.view_entry', raise_exception=True)(
            EntryPage.as_view(template='entries/page.html', access=Glue.Access.CHANGE)
        ),
    ),
]
```

`access=` sets the component's maximum Glue capability; it is not a Django
permission check. The URL decorator controls page access, and
`is_authorized()` uses the current request for both the first render and
subsequent operations. For an object-specific rule, check the component's
signed identity and the current database scope inside `is_authorized()`.

An action may return another component for a host to mount. The returned
component owns its declared child form or formset:

```python
class EntryModal(Glue.Component):
    template = 'entry/modal.html'

    @Glue.property
    def entry(self):
        return Glue.model(target=..., form=EntryForm)
```

The host disposes the modal when it closes. Disposal also removes its owned
children and listeners.

See [declared events](advanced/event_listeners.md) for `$on()` and DOM event
delivery. The template tag has no special event-handler or Alpine-bound
parameter syntax.
