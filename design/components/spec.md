# Component System (Prototype)

Status: Accepted design; implementation pending

Date: 2026-09-18

Governs: composition, stamping, mounting, and rendering of Glue components on
the **current** wire.

## Scope and relationship to `reactive-system/`

`reactive-system/component-system.md` specifies the component system as it will
exist on the redesigned wire — addressed objects, signed `target.parameters`,
`state_snapshot`, per-address failure, and the flat `objects` envelope. That wire
does not exist and is deferred (see `../REINTEGRATION.md`).

**This document governs the component work now.** It specifies a component layer
built on the wire the repository actually has: the `manifest_list` envelope,
`GluePolicy` with `identity`, `GlueAttributeCollector`, and
`GlueObjectAttribute`. Where the two documents disagree about mechanism, this one
wins for anything on the `v1.1/components` branch.

The disagreement is deliberate and bounded. This prototype does not invent a
second design; it implements the parts of the component design that do not
require the new wire, and defers the rest explicitly rather than approximating
it. Every deferral is recorded in `../REINTEGRATION.md` as a named seam.

## Context

The component design's motivating problems, from
`reactive-system/component-system.md` §Context:

1. Child identity is a hand-written global string
   (`f'time_entry_day_{date:%Y_%m_%d}'`). The `entries.new` name collided with the
   parent's `entries` collection.
2. Template inputs are Django context variables holding the *text* of a
   JavaScript identifier (`glue_form='glueForm'`). A one-character difference
   silently breaks reactivity.
3. Invalidation is a stringly-typed window event (`refresh-week-view`) that
   rebuilds a whole week for a one-field edit.
4. There is no mount/hydration signal; E2E tests carry `wait_for_timeout(300)`.
5. Server-rendered HTML is applied by replacement, destroying Alpine scopes and
   local UI state.

This prototype targets **1, 2, and 5**. Problems 3 and 4 require `$refresh()` and
declared events, which are `state-model.md` §7 contracts and genuinely blocked on
the new wire.

### What the current wire already provides

Verified against `v1.1/base`:

- **Nested Glue objects.** `GlueAttributeCollector` walks
  `inspect.getmembers_static(owner_class)`, calls `getattr` on each declared
  attribute, and wraps any value that is a `BaseGlue` in `GlueObjectAttribute`.
  Returning a configured `ModelGlue` or `QuerySetGlue` from a `Glue.property`
  already works.
- **Glue objects in call results.** `GlueResponse._serialize_glue_values` walks
  the response payload and renders any `BaseGlue` as `value.manifest.model_dump()`,
  recursing through dicts and lists. The client detects these by
  `is_glue_manifest` and builds a proxy.
- **Newly introduced objects in responses.** `GlueTemplateResponse` renders a
  template response and collects every Glue object registered *during that
  render*, returning `{'is_glue_template_response': True, 'html', 'manifest_list'}`.
  The client calls `loadManifests()` on it.
- **Proxy registration.** The client registers each manifest at
  `Glue[namespace][name]`, reading both from the signed policy.

The composition chain therefore already exists end to end: a component's
`render()` returns a `GlueTemplateResponse`; rendering its template stamps nested
components; those register into `GlueContextManager`; the response carries
`{html, manifest_list}`; the client registers the new proxies and applies the
HTML. The only missing piece is applying that HTML with morph instead of
replacement.

## Decision

### 1. A component is a `BaseGlue` subclass that owns a template path

```python
class TimeEntryDay(Glue.Component):
    template = 'time_tracker/component/day.html'
```

The template path is declared on the class. Glue receives template paths only and
never holds markup or styling. The render context comes from
`get_context_data()`, which by default exposes the component instance as
`component` and the framework-supplied `glue_attrs` (§3).

### 2. Components are registered by tag name, not by namespace

Every component shares the class-level `namespace = 'component'`, so
`GlueClassRegistry` — which maps one namespace to one class — is untouched.
Reconstruction is two-stage:

1. `GlueClassRegistry` resolves `'component'` to the `Component` base.
2. The base reads `identity['tag_name']` and resolves the concrete class through
   a separate component registry.

The signed identity carries the **registered tag name**, never an import path.
Reconstruction is therefore a registry lookup that fails closed on an unknown
name, consistent with the repository's existing preference for allowlists over
dynamic import.

`tag_name` defaults to the kebab-case class name (`TimeEntryDay` →
`time-entry-day`) and may be overridden for a domain-qualified or collision-free
public name.

Classes register through `__init_subclass__` on `Glue.Component`. Because a class
that is never imported never registers, Glue autodiscovers a `components` module
per installed app, following Django's admin autodiscovery convention. A Django
system check rejects two classes claiming the same effective tag name at startup
rather than resolving by import order.

### 3. Components are stamped with a Django template tag

```django
{% load glue %}

{% for date in component.dates %}
    {% glue_component 'time-entry-day' date=date user_id=component.user_id key=date %}
{% endfor %}
```

This **supersedes** `component-system.md` §5's `<glue:time-entry-day />` element
grammar for the prototype. The element grammar exists largely to recover typed
values from HTML attribute strings, which requires a `DjangoTemplates` subclass,
an HTML-context-aware scanner that skips `script`, `style`, comments and
`verbatim`, and a quote-aware multiline attribute parser. A Django template tag
needs none of that: `FilterExpression` resolves each kwarg to a real Python value,
so `date=date` delivers a `datetime.date`. The typed-value requirement is met by
construction rather than by parsing.

Consequences of the tag form, all intentional:

- The tag name is `glue_component`, not `component`, so projects using
  django-components are unaffected.
- The first positional argument is the registered tag name. The class resolves at
  render time through the component registry; an unknown name is an error.
- All other kwargs are parameters, validated against the component's declared
  parameters (§4). An undeclared name is an error.
- `key` is reserved and is not a parameter.
- `access` is reserved (§9).

**Self-closing only.** The block form is reserved but not implemented: a
`{% glue_component %}` … `{% endglue_component %}` pair parses and raises an
explicit "slots are not supported yet" error, so the grammar is claimed and the
boundary is visible rather than surfacing as an unknown-tag failure. See
§Deferred for why.

### 4. Parameters are the only way in

Parameters are declared with `Glue.attr(parameter=True)` and the constructor is
generated from those declarations. The hand-written `__init__` that the current
dashboard carries goes away.

```python
class TimeEntryDay(Glue.Component):
    template = 'time_tracker/component/day.html'

    date: datetime.date = Glue.attr(parameter=True)
    user_id: int = Glue.attr(parameter=True)

    @Glue.property
    def total_hours(self) -> float:
        return sum(entry.allocated_hours for entry in self._entries)
```

```python
TimeEntryDay(date=d, user_id=5)                 # ok
TimeEntryDay(date=d, user_id=5, total_hours=8)  # error: not a parameter
TimeEntryDay(date=d)                            # error: requires 'user_id'
```

On this wire, `parameter=True` means **accepted by the generated constructor and
written into the signed `policy.identity`**. That is not a legacy mechanism
wearing a specification name: identity is defined as what is required to
reconstruct the object, which is exactly what a reconstructor parameter is. When
the new wire arrives, these values move from `identity` to `target.parameters`
without changing their meaning.

`editable=True` is **not** implemented. Editable state on this wire remains the
existing `StateAttribute` / `_load_client_state` path.

#### Parameter values

A parameter value must be supported by `GlueResponseJSONEncoder`, because it is
serialized into the signed token and decoded on reconstruction. Parameters are
validated at construction and **coerced back to their declared annotation** on
reconstruction.

Coercion is required, not optional. Without it `self.date` is a `datetime.date`
on first render and a `str` after any interaction — a defect that surfaces far
from its cause. Per-parameter custom serializers are `state-model.md` §7 work and
are out of scope; a parameter whose type the encoder cannot round-trip is an
error at declaration.

### 5. `mount()`

`mount()` is the single initial-introduction hook. Glue calls it after the
generated constructor has assigned parameters and after the component is bound to
the request, but before its first policy token and initial render.

Glue does **not** call `mount()` when reconstructing from a verified token. The
distinction is available on this wire without new machinery: construction by the
template tag is introduction, construction by `_reconstruct_from_policy` is not.

Because this wire has no signed `children` map, a stamped component re-mounts on
every full page render. That is correct behavior — `component-system.md` §4
already specifies that `mount()` runs again on a new page load — but it means
`mount()` is unsuitable for exactly-once side effects, which was already true.

### 6. Composition has two distinct relationships

This is the prototype's most important structural departure from
`component-system.md` §7, where every addressed object is an independent island.
Here there are two mechanisms, and which one applies depends on how the child
came to exist.

#### Declared children embed

A `Glue.property` returning a configured Glue object is discovered by
`GlueAttributeCollector` and wrapped in `GlueObjectAttribute`. The child's state
and metadata travel **inside** the owner's manifest, and the child is named
`f'{owner.name}.{attribute_name}'`.

```python
class ChatPanel(Glue.Component):
    @Glue.property
    def chats(self) -> QuerySetGlue:
        return Glue.queryset(
            target=Chat.objects.by_user(self.request.user).active(),
            fields=['id', 'name'],
            access=Glue.Access.DELETE,
        )
```

**A child's policy must not enter the owner's signed `identity`.**
`BaseGlue._build_identity_from_attributes` currently embeds a nested Glue object's
entire `policy.model_dump()` into the owner's identity. Identity is signed on
every request, so N children multiply the owner's token by N. Declared children
embed in `state` and `metadata` only. This is the one place where embedding's cost
is unbounded rather than merely awkward.

#### Stamped components are flat

A `{% glue_component %}` inside a `{% for %}` is not a class attribute and cannot
be discovered by `inspect.getmembers_static`. Making it discoverable would require
a parallel render-time child-collection mechanism.

Instead, the tag constructs the component and registers it through
`GlueContextManager.add_glue`, producing its own top-level manifest. Parent and
child are related by *template*, not by policy.

This is closer to `state-model.md` §7's independent islands than embedding is, so
it is cheaper to reintegrate, not more expensive. What it does not provide is
ownership: there are no owner edges, so there is no owner-driven disposal. See
§10 and `../REINTEGRATION.md`.

### 7. Names are generated, deterministic, and parent-scoped

The tag derives each stamped component's name. Application code never writes one,
which removes motivating problem 1 at its source.

The name is derived from `(parent_name, tag_name, canonical(key))` and hashed to a
JavaScript-safe identifier. Two properties are required:

- **Deterministic and stable across renders** for the same logical child. A name
  derived from a counter or a random value creates a new proxy on every render and
  defeats morph. This is `component-system.md` §5's key contract arriving through
  a different door: a key must stay the same for the same logical child, and a
  loop index is never a key.
- **Parent-scoped.** The tag reads the enclosing component from the render context
  — §5's *"the compiled stamp establishes parentage from the render context"*.
  Without the parent segment, two dashboards on one page showing the same dates
  collide, and the only fix is hand-written disambiguating keys.

What this produces is a **flat address**: `component-system.md` derives an address
from owner, canonical path, family, and key, and this implements all of it except
that the owner segment is baked into a hash rather than kept as a traversable
path. Reintegration replaces the hash with a real address; it does not replace the
scheme.

`key` is required when the tag renders inside a Django `forloop`, and rejected
when it names `forloop.counter` or `forloop.counter0`. Duplicate
`(parent, tag_name, key)` triples under one parent are an error.

### 8. Rendering is state-first; replacement is morphed

#### The tag emits the component's own root

The tag supplies `glue_attrs` into the component's render context, and the
component template places it on its single root element:

```django
{# time_tracker/component/day.html #}
<div class="day-card" {{ glue_attrs }}>
    <h3>{{ component.date }}</h3>
    <p x-text="$glue.total_hours"></p>
    <button @click="$glue.add_entry()">Add</button>
</div>
```

`glue_attrs` renders the Alpine binding and the root marker:

```html
<div class="day-card" x-data="Glue.component.time_entry_day_a3f9b2" data-glue="time_entry_day_a3f9b2">
```

The alternative — rendering the template and splicing attributes into the root's
opening tag server-side — is rejected. The entire reason the tag form beats the
element form is that it never parses HTML, and splicing reintroduces exactly that:
locating an element in rendered output while tolerating comments, doctypes,
leading whitespace, and conditional roots.

Rendering a component whose output never consumed `glue_attrs` is an error. This
turns the mechanism's only real failure mode — forgetting the marker — into a
loud one instead of a component with no reactivity.

A wrapper element is also rejected: it puts the Alpine scope and the morph
boundary on different nodes, which is the split that makes stamp-scoped behavior
fragile. One component, one root, one identity.

`$glue` resolves to the proxy bound in the enclosing Alpine scope. It must not
re-read `Glue.component.<name>`, because that registration is a getter that
constructs a **new** proxy on every access.

#### Steady state flows through state, not HTML

Per `component-system.md` §3: *"Rendering is state-first. A component is
server-rendered at mount. Steady-state updates flow through state and Alpine
bindings."*

Callables return state; `process_attribute_call` already returns
`{policy_token, state, metadata}` with the result. `render()` is a separate
declared attribute, used for mount and for structural change — the dashboard's
`next_week()`, where the week's shape changes and new children are stamped.
Re-rendering a whole card to change one number Alpine could have bound directly is
not the contract.

#### Replacement is always morphed

Per `component-system.md` §6: *"Server-rendered HTML that replaces existing
content is always applied with `Alpine.morph`; glue never replaces DOM any other
way. Insertion stays plain insertion."*

The replacement surface is two implementations:

- `htmlResult.js` — `renderInnerHtml` / `renderOuterHtml`
- `view.js` — `renderInnerHtml` / `renderOuterHtml` (`proxies/template.js`
  delegates here and has no DOM code of its own)

Both switch to morph. The four `renderInsertAdjacentHtml*` methods are insertion
and are unchanged. A component template must have a single root element, and
third-party-owned subtrees opt out with an ignore attribute.

This changes behavior for existing `render_as_html` callers, which is intended:
preserving replacement would preserve motivating problem 5.

### 9. Access

A component defaults to `GlueAccess.VIEW`, overridable at the stamp site:

```django
{% glue_component 'time-entry-day' date=date access=Glue.Access.CHANGE %}
```

Callables opt into higher access through the existing `required_access` on the
attribute, checked by `process_attribute_call` against the signed policy.

`authorize()` is **not** implemented. `state-model.md` §3 specifies it as a pure
predicate at introduction, reconstruction, and attribute invocation; two of those
three call points are defined by the new wire's lifecycle. A partial version would
record a weaker contract under the specification's name.

### 10. Lifecycle is a DOM-liveness sweep, not disposal

Flat registration has no owner edges, so nothing removes a stamped component when
its DOM disappears. `next_week()` re-renders the dashboard, stamps seven new day
cards, and leaves seven dead registrations behind; navigating a month leaks
dozens.

After a morph, the client sweeps the registry and drops entries whose
`data-glue` root is no longer in the document.

**This is a DOM-liveness heuristic, not `state-model.md` §7 disposal.** It cannot
dispose non-rendered objects, it does not cascade, and it has no generation
tracking. It must be **deleted** when real ownership arrives, not extended.

### 11. Callable results may return configured Glue objects

An authorized callable may return one already-configured `BaseGlue` object; the
existing response pipeline serializes it as a manifest and the client registers a
proxy. This replaces hand-rolled transport splicing such as the dashboard's
`_build_time_entry_payload`.

```python
class TimeEntryDay(Glue.Component):
    @Glue.attr(required_access=Glue.Access.ADD)
    def new_entry(self, request: HttpRequest) -> ModelGlue:
        return Glue.model(
            target=TimeEntry(period=self.date, user=request.user),
            access=Glue.Access.ADD,
            fields=['id', 'period', 'project', 'allocated_hours'],
        )
```

The lifecycle half of `component-system.md` §8 is **not** implemented: no transient
keys beneath a caller's address, no capping of the result's capability by the
caller's, no owner-cascade disposal. A returned object registers flat like any
stamped component and is reclaimed by §10's sweep if it renders, or leaks until
page unload if it does not.

Glue does not turn a raw Django model, form, or queryset into a live Glue object
by inspecting its runtime type, and does not recursively search containers for
hidden Glue objects.

## Wire adjustments

The prototype adjusts the current wire in four places and no others.

1. **Non-registering construction.** `Glue.model`, `Glue.form`, `Glue.queryset`,
   `Glue.formset` and `Glue.sequence` currently require `request` and
   `unique_name` and register through `Glue.object`. Both become optional, so the
   same shortcut returns an unbound, unregistered object for use as a declared
   child or callable result. This implements a contract
   `component-system.md` §4 already states; it is additive and breaks no caller.
   Production code currently constructs `ModelGlue(...)` directly for want of it.
2. **Morph replaces replacement** in the two client call sites listed in §8.
3. **Child policies leave owner identity** — `_build_identity_from_attributes`
   stops embedding a nested object's `policy.model_dump()` (§6).
4. **`TemplateGlue` is removed.** It overlaps components and the roadmap already
   records its removal as a settled security finding. Removal touches
   `shortcuts/glue.py`, `glue/objects/django/template.py`, the registry entries,
   `proxies/template.js`, and two test modules.

   Known consumers, surveyed across the sibling repositories: none in
   `stratusadv-portal`, `django-spire`, `limelight`, `tradesman-mfg`, or
   `moonlite-system-portal`; **two call sites in `parhelion`**
   (`fixtures/seeded/views.py`, `fixtures/pilot/catalog/views.py`). Those are
   fixture views and both are straightforward ports, but they must be migrated
   alongside the removal rather than discovered afterwards.

## Deferred

Each deferral is a named seam in `../REINTEGRATION.md`.

- **Slots.** The block tag is mechanically cheap — parse a nodelist, render it in
  the parent's context, pass the result into the child's context. The cost is
  lifetime, not mechanism: slot content is authored in the parent's template and
  rendered against the parent's context, but a child that re-renders on its own
  request has no parent render in flight. A slotted child could only never
  re-render (forfeiting the gate), cache its rendered slot (stale by
  construction), or re-render its non-slot regions only — which means tracking
  slot boundaries through morph, and collides with §6's rule that morph boundaries
  are component boundaries. That design needs observed re-render behavior as its
  input, and we do not have it yet. Slots are the first work after the gate.
- **`$refresh()`, `$on()`, declared events.** `state-model.md` §7. These are
  motivating problems 3 and 4 and need the new wire.
- **`authorize()`** (§9), **`editable=True`** (§4), **§8 lifecycle** (§11),
  **real disposal** (§10), **addresses** (§7).

## Gate

A parent component stamping N keyed child components, each owning server state,
surviving a morph.

The gate is an **E2E test in `test_project`**: stamp N children, interact with
one, and assert the others' Alpine state and DOM identity are untouched while the
interacted child updated. Alpine scope survival and morph behavior are only
observable in a browser.

The time-entry dashboard is ported into `test_project` — its three-file shape with
equivalent fixture models — as the gate's subject, because it is the design's
motivating example throughout. The **production** dashboard in `stratusadv-portal`
is refactored as a final acceptance step once the gate is green, not as the gate
itself.

Unit tests cover what has real edge cases and needs no browser: name-derivation
determinism across renders, parameter coercion round-tripping through the signed
token, duplicate tag-name rejection, `glue_attrs` non-consumption, `key` required
under `forloop`, and the reserved block-tag error.

`just test` is the regression check; the E2E is the gate.
