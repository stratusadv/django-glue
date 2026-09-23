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

Use `render()` when an action changes HTML structure. Glue reconciles addressed
state and introduced child components, then morphs the current component root.
Stable child keys preserve their proxies and Alpine state; removed roots dispose
their addresses.

See [declared events](advanced/event_listeners.md) for `$on()` and DOM event
delivery. The template tag has no special event-handler or Alpine-bound
parameter syntax.
