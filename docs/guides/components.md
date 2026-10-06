# Components

A component is a Glue object with a Django template. Put its class in a
`components.py` module or `components/` package under the components root
(default `settings.BASE_DIR`, overridable via `DJANGO_GLUE_COMPONENTS_ROOT`);
Glue resolves it lazily when its tag is used.

```python
from django_glue import Glue


class CounterCardComponent(Glue.Component):
    template = 'counter/card.html'

    start: int = Glue.ComponentParameter()
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
    {% glue_component 'gorilla/counter_card' start=start key=start %}
{% endfor %}
```

The first argument names the component as a snake_case path: an optional
directory, then the component name. The last segment names the class —
`counter_card` resolves to `CounterCardComponent` (else `CounterCard`) — and the
segments before it are a directory, so the component must live in the
`components` module or package that is a child of that directory. Glue imports
and scans it lazily on first use; the file it lives in does not matter. Named
arguments resolve as Django filter expressions, so `start=start` passes the
Python value. Only declared parameters are accepted. `key` is required inside
a loop, must remain stable for the same logical child, and cannot be a loop
index. `access` may override the component's default `VIEW` access. A component
template must render exactly one HTML root element; Glue adds its address
marker to that root.

```django
<section>
    <button @click="component.increment()">Increment</button>
    <span x-text="component.count"></span>
</section>
```

## Model and dataclass parameters

A component that represents a database row declares it by decorating a method
with `Glue.ComponentParameter`. The method is the parameter's initializer: it
turns the row's primary key into the instance the component works with, and it
applies whatever scope the component needs.

```python
class EntryModalComponent(Glue.Component):
    template = 'entries/modal.html'

    @Glue.ComponentParameter
    def entry(self, pk: int) -> TimeEntry:
        return TimeEntry.objects.active().select_related('project').get(pk=pk, user=self.request.user)
```

The method name is the parameter name, its return annotation must be a model
class, and it takes only the key. Pass the instance when you already have it, or
its key when you do not:

```python
entry = TimeEntry.objects.active().select_related('project').get(pk=entry_id, user=request.user)
return EntryModalComponent(entry=entry)
```

```django
{% glue_component 'entries/entry_modal' entry=entry.pk %}
```

- A supplied instance is used as is, with no query. A supplied key is resolved
  through the initializer on the first read of `self.entry`.
- Only the key is signed. Every later request passes it to the initializer with
  the current request, so scope is re-applied on every interaction. A row the
  initializer no longer returns fails that component with
  `model_instance_not_found`.
- A supplied instance must be loaded the way the initializer loads it, with the
  same `select_related()` and annotations. With
  `DJANGO_GLUE_VERIFY_MODEL_PARAMETERS` on (it defaults to `DEBUG`), Glue checks:
  an instance the initializer does not return raises
  `GlueComponentParameterError`, and one missing an annotation or loaded relation
  emits `GlueModelParameterMismatchWarning` and is replaced by the initializer's
  instance. Escalate the warning to an error in your test settings to catch it in
  CI.
- A callable may assign an instance or a key to retarget the component, which
  re-renders it. The initializer is never callable from the client, and a model
  parameter cannot be editable.

A value parameter annotated with a dataclass is signed as its JSON form and
restored as the dataclass, including nested dates, decimals, and enums:

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class ReportWindow:
    start: datetime.date
    end: datetime.date


class BudgetPanelComponent(Glue.Component):
    template = 'reports/budget_panel.html'

    window: ReportWindow = Glue.ComponentParameter()
```

A form is not a parameter. Build it as a child from the model parameter:

```python
@Glue.property
def entry_form(self) -> FormGlue:
    return Glue.form(target=TimeEntryForm(instance=self.entry))
```

The server template context exposes the Python component as `component`; the
mounted Alpine scope exposes its client proxy under the same name. `$glue`
resolves that proxy from an element inside the component. Outside Alpine,
`Glue.from(element)` finds the nearest component root. `component.$el` returns
its current root. Components are addressed objects and do not receive global
names under `Glue.component`.

A successful callable re-renders its component in the same response and morphs
its mounted root, so an action that saves data needs no follow-up refresh and
no `render()` call:

```python
@Glue.attr(required_access=Glue.Access.CHANGE)
def confirm(self, transaction_id: int) -> None:
    Transaction.objects.get(pk=transaction_id).confirm()
```

Two kinds of callable skip the render. A callable whose declared result is a Glue
object, such as one that returns a modal component, hands the interaction to that
object. A callable declared with `skip_rerender=True` opts out, for example one
that deletes the row its component shows:

```python
@Glue.attr(required_access=Glue.Access.DELETE, skip_rerender=True)
def delete_entry(self) -> None:
    self.entry.delete()
    Glue.event(self, 'deleted', {'pk': self.entry_id})
```

`skip_rerender` only applies to a component's own callables. Declaring it on a
model, queryset, form, service, or other Glue object raises a `TypeError` when
the class is defined, because nothing there re-renders.

A callable that changes one of the component's parameters or other retained
values re-renders regardless, so the markup always matches the component's
state. Only the component whose callable ran re-renders.

Call `component.$refresh()` when data outside that component changes, such as a
record saved by a modal. The refresh recomputes its properties and markup and
morphs the root; removed child roots dispose their addresses. To re-render when
another component announces a change, list its events in `rerender_on` (see
[declared events](advanced/event_listeners.md)). `render()` produces HTML for
initial or host mounting.

### A parent's re-render keeps its children

When a component re-renders after a page has loaded, the children it stamps
with `{% glue_component %}` and that are still on the page are kept as they are:
the server sends a placeholder for each, and the child keeps its markup, its
state, and its Alpine data. Only children that are new, or that the parent now
stamps with different parameters or access, are rendered. A child stamped with
different parameters is a new child, mounted fresh.

A kept child is only as current as its last render, so a child that shows data
another component changes declares the events that change it:

```python
class CloseProgressComponent(Glue.Component):
    template = 'close/component/close_progress.html'
    rerender_on = (TransactionRowComponent.confirmed, TransactionRowComponent.receipt_attached)
```

A child that is simply a view of data its parent re-reads, with parameters that
do not change when that data does, can instead be stamped with the
`rerender_with_parent` flag. It then renders with every render of its parent,
and is mounted fresh each time, so it keeps no state of its own between them:

```django
{% for date in dates %}
    {% glue_component 'entries/day' date=date key=date rerender_with_parent %}
{% endfor %}
```

## Use a component as a URL view

Register a component directly in Django's URL patterns with `as_view()`:

```python
from django.urls import path
from .components import CounterCardComponent

urlpatterns = [
    path('cards/<int:start>/', CounterCardComponent.as_view(), name='card-fragment'),
    path(
        'cards/<int:start>/page/',
        CounterCardComponent.as_view(layout_template='cards/page.html'),
        name='card-page',
    ),
]
```

Named URL captures supply declared component parameters. The default response
is the component's own template as an HTML fragment, for fetching with
`Glue.view(url)`. Set a layout template to respond with a full page instead:
the layout template contains the component and marks where it renders. Declare
it on the class with `layout_template`, or pass `layout_template=` to
`as_view()` to override the class attribute for one URL:

```python
class CounterCardComponent(Glue.Component):
    template = 'cards/counter_card.html'
    layout_template = 'cards/page.html'
```

A layout template does not change the component's own `template`, which it
keeps for every later re-render.

When parameters or access depend on the request, write an ordinary view that
constructs the component and responds with `as_page()`:

```python
@permission_required('entries.view_entry', raise_exception=True)
def week_view(request):
    requested = request.GET.get('date')
    week_of = datetime.date.fromisoformat(requested) if requested else timezone.localdate()
    access = Glue.Access.CHANGE if request.user.has_perm('entries.change_entry') else Glue.Access.VIEW

    component = WeekComponent(week_of=week_of, access=access)
    return component.as_page(request)
```

`as_page(request, layout_template=None)` introduces and mounts the component,
then renders its layout template, or the component alone when there is none. A
denial by `is_authorized()` responds 403. The constructor call is the whole
contract: an unknown or missing parameter raises the component's normal error.
`as_view()` is the same response for a component built from URL captures and
fixed keyword arguments.

`get_view_kwargs()` is deprecated and will be removed in 1.2.0. A component that
overrides it emits a `DeprecationWarning`; move its body into a view as above.

The layout template places the rendered component with the no-argument tag:

```django
{% extends 'base.html' %}
{% load django_glue %}
{% block content %}{% glue_component %}{% endblock %}
```

The no-argument tag renders the component supplied by `as_view()`. Outside a
component view, it raises an error. The layout template must load Glue with
`{% django_glue_init %}`, directly or through the template it extends. These URLs serve GET and HEAD; component actions use
Glue's normal addressed endpoint.

Use Django's view decorators to guard the initial URL. Override
`is_authorized()` on the component to check permission again for later Glue
calls:

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
            EntryPage.as_view(layout_template='entries/page.html', access=Glue.Access.CHANGE)
        ),
    ),
]
```

`access=` sets the component's maximum Glue capability; it is not a Django
permission check. The URL decorator controls page access, and
`is_authorized()` uses the current request for both the first render and
subsequent operations. For an object-specific rule, check the component's
signed identity and the current database scope inside `is_authorized()`.

A denial at the first render depends on how the component was created. A
component served by `as_view()` responds 403. A component stamped with
`{% glue_component %}` renders nothing and introduces no address, so the rest of
the page renders normally; the template does not need its own permission check
around the tag. A denied `@Glue.property` child resolves to absent. After the first
render, a denied action or refresh fails only that component's entry with
`not_authorized`.

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

## Server-side state (ComponentSession)

Some state a component needs is invisible to the client: a rate-limit counter,
a multi-step flow's position, a scratch value shared by the component's
instances. Signed parameters and state snapshots exist for state the client
sees, and a private field dies on every request, so Glue provides
`self.session`: a mutable mapping over one entry in the request's Django
session, scoped by the component class's qualified name (ADR 026).

```python
class OnboardingComponent(Glue.Component):
    template = 'onboarding/panel.html'

    @Glue.attr(required_access=Glue.Access.CHANGE)
    def skip(self):
        self.session['skipped'] = True
```

- The session persists itself. A change — setting a key to a value it does
  not already hold — marks the session modified, and Django saves a modified
  session when the request completes, so a request that changes nothing
  saves nothing. A write a call makes before it raises is kept.
- Every instance of the class shares the entry within one user's session;
  the state is per-user. State shared across users, or durable state,
  belongs in the database.
- The session never crosses the wire: it is not part of the policy token or
  the computed data, and the client cannot read or write it.
- Keys must be strings, and values must be serializable by your session
  backend.
