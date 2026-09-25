# Migration Guide — v1.0 to v1.1

v1.1 made **significant changes to the underlying state model** and **introduced
components**. The wire protocol, the client state model, and a few public
shortcuts changed. Existing view registrations for `Glue.model(...)`,
`Glue.queryset(...)`, and `Glue.form(...)` retain their call shape. Formsets
need an importable form class or `Glue.FormSet` subclass in place of a Django
formset instance. Other breaking changes affect declared-attribute options,
relation projection, how a model exposes its service, and the client's refresh
semantics — plus one new MIDDLEWARE entry.

Work through it in this order; each section is a self-contained pass over your
codebase.

> The full protocol specification lives in `design/specs/core/state-model.md`
> and `design/specs/core/component-system.md`. This is the practical
> before/after walkthrough for migrating a consuming app and adopting the new
> features.

## At a glance

| v1.0 | v1.1 |
|---|---|
| `@Glue.attr(..., takes_client_state=...)` / `updates_client_state=...` | delete the kwarg |
| `loading_strategy=...` / `Glue.LoadingStrategy` | delete (introduction snapshot is complete by default) |
| `related_field_config={...}` | `fields=Glue.fields(...)` with relation subfields |
| `services = Glue.attr(Service(), ...)` | `services = Glue.namespace(Service(), ...)` |
| client `await model.load_state()` | `await model.$refresh()` |
| `Glue.template(name)` / `TemplateGlue` | `@Glue.html_attr` on the object |
| `Glue.formset(..., formset_factory(...)())` | `Glue.formset(..., EntryFormSet)` with a `Glue.FormSet` subclass |
| wire `state` / `metadata` / `manifest_list` | addressed entries with `static_data` / `computed_data` |
| — | **new:** `Glue.Component` + the `{% glue_component %}` tag |
| — | `django_glue.middleware.GlueViewMiddleware` as the last `MIDDLEWARE` entry |

## In views and Python

### Declared attributes: drop the state-control kwargs

`takes_client_state` and `updates_client_state` no longer exist. The server now
signs a full state snapshot and the client round-trips an `updates` diff; whether
a value round-trips is derived from editability, not a per-attribute flag. Just
delete the kwargs — nothing replaces them.

```python
# v1.0
@Glue.attr(required_access=Glue.Access.CHANGE, takes_client_state=True)
def statistic_choices(self) -> list[dict]:
    ...

# v1.1
@Glue.attr(required_access=Glue.Access.CHANGE)
def statistic_choices(self) -> list[dict]:
    ...
```

The same applies to `@Glue.html_attr`. A read-only attribute simply omits them
rather than passing `updates_client_state=False`.

### Relation projection: `related_field_config` → `Glue.fields`

`related_field_config` is gone. Project related scalar fields with `fields=`
using `Glue.fields()`, which normalizes `relation=(sub, fields)` into the
canonical `relation__subfield` paths. Projecting a relation's subfields
automatically keeps the relation's raw identity (e.g. the FK pk) as an editable
value on the owner, so you no longer list the relation separately.

```python
# v1.0
Glue.model(
    request,
    'dashboard_time_entry_form',
    target=time_entry,
    access=access,
    fields=['id', 'period', 'partner', 'project', 'user'],
    related_field_config={
        'partner': {'fields': ['id', 'name']},
        'project': {'fields': ['id', 'name']},
        'user': {'fields': ['id', 'first_name', 'last_name', 'username']},
    },
    form=TimeEntryForm,
)

# v1.1
Glue.model(
    request,
    'dashboard_time_entry_form',
    target=time_entry,
    access=access,
    fields=Glue.fields(
        'id', 'period',
        partner=('id', 'name'),
        project=('id', 'name'),
        user=('id', 'first_name', 'last_name', 'username'),
    ),
    form=TimeEntryForm,
)
```

`fields` also accepts nested paths (`Glue.fields('name', red=('name', skills=('name',)))`
→ `name`, `red__name`, `red__skills__name`) and is accepted by `exclude=`.

### Exposing a model's service: `Glue.attr` → `Glue.namespace`

A model that exposes its service to the client must use `Glue.namespace`, not
`Glue.attr`. `Glue.attr(Service(), ...)` declared the service *instance* as a
value attribute; v1.1 validates value attributes for JSON-serializability and
rejects a live service object. `Glue.namespace` compiles the provider's
`@Glue.attr` methods into the owner's capability beneath one path.

The provider keeps its descriptor form, so `BaseDjangoModelService` subclasses
bind `obj` exactly as before:

```python
# v1.0
services = Glue.attr(TimeEntryService(), required_access=Glue.Access.DELETE)

# v1.1
services = Glue.namespace(TimeEntryService(), required_access=Glue.Access.DELETE)
```

`Glue.namespace` accepts three provider forms:

- a descriptor instance — `services = Glue.namespace(Service())` (every
  `BaseDjangoModelService` is a descriptor);
- a provider class — `services = Glue.namespace(Service)`, instantiated per
  access with the glued target;
- a method — `@Glue.namespace` on a method whose return annotation names the
  provider class.

`required_access=` is unchanged and gates the whole namespace.

### Large relations need a choice source

v1.0 returned every related row when the client asked for a relation's
choices. v1.1 raises `ImproperlyConfigured` when a relation has more than 25
choices and no configured source, because the client would otherwise download
the whole table. The client fetches a relation's choices the first time
anything reads its `.choices`, so this fires on any relation the object
exposes, including one the form never renders.

Give each large relation a searchable source with `choices=`, and stop
exposing relations the client does not need (e.g. a `user` the server sets
from `request.user`):

```python
Glue.model(
    request,
    'time_entry_form',
    target=time_entry,
    access=access,
    fields=Glue.fields('period', partner=('id', 'name'), project=('id', 'name')),
    choices={
        'partner': Glue.choices(Partner.objects.active(), search_fields=['name']),
        'project': Glue.choices(
            Project.objects.filter(status=ProjectStatusChoices.IN_PROGRESS),
            search_fields=['name'],
        ),
    },
)
```

A choice source is pickled into the signed policy and decoded through an
allowlisting unpickler. Filtering on a `TextChoices` / `IntegerChoices` member
is fine: it is issued as its plain value. Any other application type in a
filter (a custom lookup, expression, or value class) fails when the page
renders, naming the type. Filter on a plain value instead, or admit the type
with `QuerySetUnpickler.register('myapp.lookups.MyLookup')`.

### Loading strategies are gone

There is no `loading_strategy=` / `Glue.LoadingStrategy`. Every introduced
object ships a complete snapshot on introduction; there is no lazy/deferred
mode. Where a v1.0 view relied on `LoadingStrategy.EAGER` to pre-populate
related data, the same data is present on introduction — no change needed.

### Formsets are keyed collections

`Glue.formset()` now accepts an importable Django form class or a
`Glue.FormSet` subclass. It rejects a Django `BaseFormSet` instance and a
`formset_factory()` class, because the signed token must rebuild the same
formset on later requests. Define configuration and any cross-form logic on
the subclass:

```python
class EntryFormSet(Glue.FormSet):
    form_class = EntryForm
    min_num = 1
    max_num = 50
    can_delete = True

Glue.formset(request, 'entries', EntryFormSet, Glue.Access.CHANGE)
```

Rows start empty. `append(initial)` and `pop(key)` are asynchronous server
calls; signed membership carries surviving rows into later requests. A
formset action such as `save_time_entries()` can call `self.validate()` and
use each returned `FormGlue.bound_form` for Django form saving.

## In templates and JavaScript

### `load_state()` → `$refresh()`

The client no longer has `load_state()`. `$refresh()` re-derives an object's
output from its current state and reconciles the response as authoritative.
For a mounted component, it renders and morphs the component root. Application
code does not call `render()` to update a mounted component after another
object saves.

```js
// v1.0
await this.model.load_state()

// v1.1
await this.model.$refresh()
```

### Bundled Alpine and morph

Alpine.js and its morph plugin are now bundled in the `django_glue` static
assets. Remove any separately-loaded Alpine core and morph `<script>` tags and
any application call to `Alpine.start()` — consuming apps never start Alpine.

### `Glue.view(url)` and the new middleware

`Glue.view(url)` now requests the actual Django route with Glue content
negotiation; the old redispatch endpoint is gone. Register
`django_glue.middleware.GlueViewMiddleware` **last** in `MIDDLEWARE` — it
packages a rendered HTML response into the `Glue.view` envelope only for
requests that negotiate it. Startup checks fail if it is missing
(`django_glue.E003`) or present but not final (`django_glue.E002`):

```python
MIDDLEWARE = [
    # ... every other middleware ...
    'django_glue.middleware.GlueViewMiddleware',  # must be last
]
```

`renderOuterHtml()` now requires exactly one root element in the fragment.

## New: Components

v1.1 introduces **components** — server-rendered, self-contained UI units that
glue composes and keeps in sync through the same state model as models, forms,
and querysets. A component is a `Glue.Component` subclass that owns a template
path and a fixed set of typed parameters. This is the headline new capability
of the release.

### Define a component

```python
class TimeEntryDay(Glue.Component):
    template = 'time_tracker/component/day.html'

    date: datetime.date = Glue.ComponentParameter()
    user_id: int = Glue.ComponentParameter()
    note: str = Glue.ComponentParameter('', editable=True)

    @cached_property
    def _entries(self):
        return TimeEntry.objects.filter(user_id=self.user_id, period=self.date)

    @Glue.property
    def total_hours(self):
        return sum(e.allocated_hours for e in self._entries)
```

- `template` is the component's template path; `tag_name` (optional) overrides
  the default kebab-case name derived from the class after removing a trailing
  `Component` suffix.
- `Glue.ComponentParameter()` declares a **reconstructor** supplied at
  construction (from the template tag or Python). It is a shorthand for
  `Glue.attr(parameter=True)`.
- `Glue.ComponentParameter(x, editable=True)` is editable state: supplied at
  construction and updatable by the client through its admitted channel.
- `Glue.attr(x, editable=True)` is internal draft state, not a parent input.
- `@Glue.property` is derived output, recomputed server-side.

Components are **closed systems**: parents pass parameters; they do not reach
in and assign child state (`day_glue.entries = ...` goes away). The constructor
is generated from the declarations, so a hand-written `__init__` is not needed.
`TimeEntryDay(date=d, user_id=5)` works; passing a non-parameter
(`total_hours=8`) or omitting a required one is an error.

### Stamp a component

Components are mounted with the `{% glue_component %}` template tag. The first
positional expression names the registered component; named expressions resolve
through Django's `FilterExpression` (Python types preserved). `key` and `access`
are reserved; every other named expression must be a declared parameter. A
component inside a loop needs a stable explicit `key` (`forloop.counter` is
rejected).

```django
{% load django_glue %}
{% for date in component.dates %}
    {% glue_component 'time-entry-day' date=date user_id=component.user_id key=date %}
{% endfor %}
```

The `key` fixes a stable child address under the composing parent; the class's
registered tag name drives reconstruction. A component mounts during the render
that stamps it. Parameter changes and `$refresh()` render and morph mounted
HTML with `Alpine.morph`. Components are discovered from each installed app's
`components` module or package at startup.

Components reuse the established `BaseGlue` entry points — the same signed
parameters, state snapshots, editable-update admission, unsigned response data,
effects, and client reconciliation as the other families. They are a
composition layer over `BaseGlue`, not a new state engine.

## In tests and internal-API consumers

If your tests drive the resolver directly, the internal surface changed:

- `BaseGlue.process_attribute_call(context)` returns a tuple
  `(entry, introduced)`, not a response. Unpack it:
  `payload, _introduced = glue_object.process_attribute_call(context)`.
  `payload` is the addressed entry **dict** — no `.content` / `json.loads`.
- The request context field `target_glue_client_state` is now
  `target_glue_updates`, and values are **flat** (no `{'path': {'value': ...}}`
  envelope): `target_glue_updates={'start_date': '2025-02-01', ...}`.
- Entries no longer carry `state` / `metadata` / `manifest_list`. Down-only
  data is `static_data` (stable interface) and `computed_data` (derived
  output); each is omitted when unchanged, and **omission means the client's
  previous value stands**.
- An HTML attribute's `result` is
  `{'is_glue_template_response': True, 'html': ..., 'objects': [...]}`.

## What did not change

- `Glue.function(request, name, 'dotted.path')` is unchanged and remains the
  way to expose a plain Python callable by import path.
- The shortcut call order is unchanged: `(request, name, target, access, ...)`.
  The name keyword is now `unique_name` (positional is unaffected).
- `{% django_glue_init %}` and the `Glue.model.<name>` / `Glue.querySet.<name>`
  client namespaces are unchanged.
- `@Glue.attr` / `@Glue.html_attr` on model, form, and queryset objects is the
  same declared-attribute surface; only the removed kwargs above differ.
