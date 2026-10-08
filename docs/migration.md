# Migration Guide — v1.1 to v1.2

v1.2 changes how a component is set up, when it re-renders, and how a formset
saves. Models, querysets and forms registered with `Glue.model(...)`,
`Glue.queryset(...)` and `Glue.form(...)` need no changes.

Most of the removed names raise an error that names their replacement, when the
class is defined or when Django starts, so they are hard to miss. The two
changes that fail silently are
[a parent no longer redraws its children](#a-parents-re-render-keeps-its-children)
and [a formset saves nothing when a row is invalid](#formsets-save-all-rows-or-none).
Check those by hand.

Coming from v1.0? Do [v1.0 to v1.1](#migration-guide-v10-to-v11) below first.

## At a glance

| v1.1 | v1.2 |
|---|---|
| `get_view_kwargs(cls, request, **url_kwargs)` | `__post_init__(self, request)`, assigning parameters and `self.access` |
| `get_context_data(self)` | `{{ component.<name> }}` in the template; `self.context_data` for page context |
| `mount(self)` | `__post_init__(self, request)` (`mount` still runs, and warns) |
| `layout_template` | `view_template` |
| `return self.render()` from a callable | return nothing; the component re-renders by itself |
| `await component.save()` then `await component.$refresh()` | `await component.save()` |
| a parent's re-render redraws its children | the child declares `rerender_on`, or is stamped with `rerender_with_parent` |
| `DJANGO_GLUE_COMPONENTS_ROOT = <root>` | `DJANGO_GLUE_COMPONENTS = {'DIRS': [<root>]}` |
| `from django_glue.glue.component import Component` | `from django_glue.glue.components import Component` |
| `formset.save()` saves the valid rows | saves every row or none |
| `formset.append({'owner': pk})` for a field the form does not expose | `new_row_defaults={'owner': pk}` |
| — | **new:** `Component.session` and `Glue.SessionAttr` |
| — | **new:** `Glue.listener`, model parameters, formsets that edit saved records |

## Components

### One setup hook: `__post_init__`

`get_view_kwargs()`, `mount()` and `get_context_data()` are replaced by one
method, `__post_init__(self, request)`. It runs once, when the component first
appears on a page, after the user is authorized and before the first render.

```python
# v1.1
class WeekComponent(Glue.Component):
    template = 'entries/week.html'
    layout_template = 'entries/page.html'

    week_of: datetime.date = Glue.ComponentParameter()
    entry_count: int = Glue.attr(0)

    @classmethod
    def get_view_kwargs(cls, request, **url_kwargs):
        return {'week_of': datetime.date.fromisoformat(request.GET['date'])}

    def mount(self):
        self.entry_count = TimeEntry.objects.in_week(self.week_of).count()

    def get_context_data(self):
        return {
            **super().get_context_data(),
            'page_title': f'Week of {self.week_of:%B %-d}',
            'entries': TimeEntry.objects.in_week(self.week_of),
        }

# v1.2
class WeekComponent(Glue.Component):
    template = 'entries/week.html'
    view_template = 'entries/page.html'

    week_of: datetime.date | None = Glue.ComponentParameter(None)
    entry_count: int = Glue.attr(0)

    def __post_init__(self, request):
        if self.week_of is None:
            self.week_of = datetime.date.fromisoformat(request.GET['date'])

        self.entry_count = TimeEntry.objects.in_week(self.week_of).count()
        self.context_data['page_title'] = f'Week of {self.week_of:%B %-d}'

    @cached_property
    def entries(self):
        return list(TimeEntry.objects.in_week(self.week_of))
```

Move each hook's code as follows:

- **`get_view_kwargs`.** The component is now constructed before the hook
  runs, so a parameter the request supplies needs a default. Assign it in
  `__post_init__` when it was not passed. Set the access level there too, with
  `self.access = Glue.Access.CHANGE`. A URL capture or `as_view()` argument
  that is not a declared parameter arrives as a keyword of the hook:
  `def __post_init__(self, request, pk: int)`.
- **`mount`.** Rename it to `__post_init__(self, request)`. An overridden
  `mount()` still runs, before `__post_init__`, and emits a
  `DeprecationWarning`.
- **`get_context_data`.** A component's template context on a re-render is
  `component` alone. Read what the component's own template shows from the
  component, and put what the page around it needs in `self.context_data`:

```django
{# v1.1 #}
{% for entry in entries %}...{% endfor %}

{# v1.2 #}
{% for entry in component.entries %}...{% endfor %}
```

`context_data` exists for the first render and the view template only. A
callable that changes it raises an error.

A class that still defines `get_view_kwargs`, `get_context_data` or
`layout_template` raises `TypeError` when it is defined.

### `layout_template` is `view_template`

Rename the class attribute and the `as_view()` argument:

```python
# v1.1
path('cards/', CounterCardComponent.as_view(layout_template='cards/page.html'))

# v1.2
path('cards/', CounterCardComponent.as_view(view_template='cards/page.html'))
```

### A callable re-renders its component

A successful component callable now re-renders its component in the same
response. Remove the code that did it by hand:

```python
# v1.1
@Glue.attr(required_access=Glue.Access.CHANGE)
def confirm(self, transaction_id: int):
    Transaction.objects.get(pk=transaction_id).confirm()
    return self.render()

# v1.2
@Glue.attr(required_access=Glue.Access.CHANGE)
def confirm(self, transaction_id: int) -> None:
    Transaction.objects.get(pk=transaction_id).confirm()
```

```js
// v1.1
await component.confirm(id)
await component.$refresh()

// v1.2
await component.confirm(id)
```

A callable that deletes the row its component shows would now fail while
re-rendering it. Declare it with `skip_rerender=True`:

```python
@Glue.attr(required_access=Glue.Access.DELETE, skip_rerender=True)
def delete_entry(self) -> None:
    self.entry.delete()
    Glue.event(self, 'deleted', {'pk': self.entry_id})
```

A callable whose declared result is a Glue object, such as one that returns a
modal component, does not re-render either. `$refresh()` is still the way to
redraw a component when data outside it changes.

### A parent's re-render keeps its children

In v1.1 a component that re-rendered stamped its children again, so they
redrew with it. In v1.2 the children still on the page are kept as they are,
with their state and Alpine data. **A child that relied on its parent to
refresh it now shows what it last rendered**, and nothing raises.

For each child that shows data another component changes, choose one:

```python
# The child names the events that change it.
class CloseProgressComponent(Glue.Component):
    template = 'close/component/close_progress.html'
    rerender_on = (TransactionRowComponent.confirmed,)
```

```django
{# Or the child renders with every render of its parent, keeping no state. #}
{% glue_component 'entries/day' date=date key=date rerender_with_parent %}
```

A child stamped with different parameters is a new child and is rendered
fresh, as before.

### `DJANGO_GLUE_COMPONENTS_ROOT` is `DJANGO_GLUE_COMPONENTS`

```python
# v1.1
DJANGO_GLUE_COMPONENTS_ROOT = BASE_DIR / 'app'

# v1.2
DJANGO_GLUE_COMPONENTS = {'DIRS': [BASE_DIR / 'app']}
```

A project that still sets the old name fails the system check
`django_glue.E004`. A project that never set it needs no change: `DIRS`
defaults to `[BASE_DIR]`. Installed apps are now searched as well, so a
library's components resolve without configuration.

### The component modules moved

`Glue.Component` is unchanged. Only direct imports need updating:

| v1.1 | v1.2 |
|---|---|
| `django_glue.glue.component` | `django_glue.glue.components.component` |
| `django_glue.glue.component_registry` | `django_glue.glue.components.registry` |
| `django_glue.glue.component_discovery` | `django_glue.glue.components.discovery` |
| `django_glue.glue.component_naming` | `django_glue.glue.components.naming` |
| `django_glue.glue.component_root` | `django_glue.glue.components.root` |
| `django_glue.glue.component_tag` | `django_glue.glue.components.tag` |

`Component` and `component_registry` also import from
`django_glue.glue.components`.

## Formsets

### Formsets save all rows or none

`await formset.save()` now validates every row first. **If any row is invalid,
nothing is saved**; v1.1 saved the valid rows. A page that relied on a partial
save needs to show the row errors and let the user save again.

`save()` also no longer calls each row form's own `save`. It passes the
validated Django forms to `save_forms`, so a form class that overrode `save` to
write through a service moves that code to a `Glue.FormSet` subclass:

```python
class SkillFormSet(Glue.FormSet):
    form_class = SkillForm

    def save_forms(self, form_list):
        for form in form_list:
            form.instance.services.save_model_obj(**form.cleaned_data)
```

### `append(initial)` only takes fields the user can edit

`await formset.append(initial)` rejects any key that is not a field the form
lets a user edit. v1.1 accepted every key, so a browser could set any model
field on a new row. Values the user must not choose, such as the key of the
record the rows belong to, move to the server:

```python
# v1.1, in JavaScript: await formset.append({red_corner: gorillaId})

# v1.2
Glue.formset(
    request,
    'fights',
    FightNameForm,
    Glue.Access.DELETE,
    new_row_defaults={'red_corner': gorilla.pk},
)
```

## New in v1.2

Nothing here is required to upgrade.

- **Component sessions.** `self.session` is a per-user mapping kept in the
  Django session, for state the client should not hold.
  `step: int = Glue.SessionAttr(0)` declares a value stored there that the
  client can read. See the
  [components guide](guides/components.md#server-side-state-componentsession).
- **Events between components.** `rerender_on` re-renders a component when
  another emits an event, and `@Glue.listener` runs a method first. See
  [declared events](guides/advanced/event_listeners.md).
- **Model parameters.** `@Glue.ComponentParameter` on a method turns a signed
  primary key into the row, so a parent can hand a loaded record to a child.
- **Formsets that edit saved records.** `instances=` loads saved records as
  rows, and removing one deletes it on the next `save()`. See the
  [form guide](guides/form_glue.md#editing-saved-records).

## In tests

- A component constructed without a `name` is named after its class, as
  `as_view()` already named it. A test that looked a component up under the
  shared name `component` uses the class-derived name.
- A component stamped by `{% glue_component %}` that `is_authorized()` denies
  renders nothing instead of failing the page. A test that expected the page to
  fail checks that the component is absent.

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

### Save methods that both create and update: `Glue.Access.required_save_access`

A draft from `queryset.new()` now has exactly `ADD` access, whatever the
queryset's access. In v1.0 it inherited the queryset's access, usually `CHANGE`.
A form method that saves both new and existing instances therefore cannot
require a fixed `CHANGE`: a draft opened from an "Add" button would be rejected.
Declaring a fixed `ADD` instead would let a create-only object modify persisted
rows. Pass `Glue.Access.required_save_access`, which requires `ADD` while the
instance is unsaved and `CHANGE` once it is persisted:

```python
# v1.0
@Glue.attr(required_access=Glue.Access.CHANGE)
def save_model_obj(self, request: HttpRequest) -> GlueResponse:
    ...

# v1.1
@Glue.attr(required_access=Glue.Access.required_save_access)
def save_model_obj(self, request: HttpRequest) -> GlueResponse:
    ...
```

Glue's own `save()` and `validate()` on forms, and `save()` on models, use the
same rule. A method that only ever edits persisted instances can keep
`Glue.Access.CHANGE`.

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

- `template` is the component's template path. The component is addressed in
  templates by a snake_case path (see "Stamp a component"), not by a name the
  class declares.
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
positional expression names the component as a snake_case path — an optional
directory, then the component name; the last segment maps to the class
(`time_entry_day` → `TimeEntryDay(Component)`) and the component must live in
the `components` module or package under that directory. Named expressions
resolve through Django's `FilterExpression` (Python types preserved). `key` and
`access` are reserved; every other named expression must be a declared
parameter. A component inside a loop needs a stable explicit `key`
(`forloop.counter` is rejected).

```django
{% load django_glue %}
{% for date in component.dates %}
    {% glue_component 'time_tracker/time_entry_day' date=date user_id=component.user_id key=date %}
{% endfor %}
```

The `key` fixes a stable child address under the composing parent; the class's
`module.qualname` drives reconstruction. A component mounts during the render
that stamps it. Parameter changes and `$refresh()` render and morph mounted
HTML with `Alpine.morph`. Components are resolved lazily when their tag is used,
from the `DIRS` of `DJANGO_GLUE_COMPONENTS` (default `[settings.BASE_DIR]`) and
then from the installed apps.

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
