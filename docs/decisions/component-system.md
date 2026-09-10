# Component System

Status: Accepted (direction); implementation pending

Date: 2026-09-10

## Context

Django Glue already solves the backend/frontend contract: signed, stateless
policies (`glue/policy.py`), declared attributes (`@Glue.attr`,
`@Glue.property`), nested glue objects (`GlueObjectAttribute`), a namespace
registry (`glue/registry.py`), and a round trip that can return state, new
manifests, and HTML.

The time entry dashboard in stratusadv-portal
(`app/time_tracker/glue/dashboard/`) proves the ViewModel half of a component
system works: one `Glue.object()` call in the view, one
`Glue.timeEntryDashboard` binding in `x-data`, and commands such as
`next_week()` that mutate `self` and return `{}` so the state diff is the
payload.

What still hurts is composition:

- Child identity is a hand-written global string
  (`f'time_entry_day_{date:%Y_%m_%d}'`, `f'{self.name}.entries.new'`). The
  `entries.new` name collided with the parent's `entries` collection and
  forced `updates_client_state=False` on `TimeEntryDayGlue.new_entry`.
- Template inputs are Django context variables holding the *text* of a
  JavaScript identifier (`glue_form='glueForm'`). A one-character difference silently
  breaks reactivity; a library rename shipped a broken modal.
- Invalidation is a stringly-typed window event (`refresh-week-view`) that
  rebuilds the whole week for a one-field edit.
- There is no mount/hydration signal; E2E tests carry
  `wait_for_timeout(300)` for the Alpine binding race.
- Server-rendered HTML is applied by replacement (`GlueHtmlResult`,
  `GlueView`, `GlueTemplateProxy`), which destroys Alpine scopes and local UI
  state.

Tetra, django-unicorn, django-components, and Lit were evaluated and rejected
(see Rejected Alternatives). **Blazor** is the reference programming model: a
full-stack reactive component framework with parameters flowing down and
events flowing up. **Livewire** is the reference for the mechanism of
server-driven components over Alpine with morphing.

## Decision

### 1. The component system lives in django-glue

Glue owns the component system end to end. Glue objects receive **template
paths only**; glue never holds template definitions, markup, or styling. That
keeps presentation with the consuming project and django-spire, and is the
same arrangement `TemplateGlue` already uses.

### 2. Alpine.js is a dependency of glue's client

Glue's JavaScript client may call `Alpine.reactive`, `Alpine.morph`,
`Alpine.data`, `Alpine.addScopeToNode`, and hook Alpine's lifecycle. The
Python side remains framework-free.

This retires the layering rule *"Glue core must not reference any frontend
framework."* Glue was already designed around Alpine — per-access proxy
construction, `_mergeState`, and GLUE-93 are all reasoned in Alpine's terms —
while being forbidden from using Alpine's affordances.

### 3. A component is a `BaseGlue` subclass that owns a template path

```python
class TimeEntryDay(ComponentGlue):
    template = 'time_tracker/component/day.html'
```

- The template path is declared on the class, with a constructor override.
- The render context comes from `get_context_data()`, which by default
  exposes the component instance.
- **Rendering is state-first.** A component is server-rendered at mount.
  Steady-state updates flow through state and Alpine bindings, exactly as the
  dashboard works today. `render()` exists for mount and for dynamic insertion
  (modals, fragments, and structural change such as a new week).

### 4. Components are closed systems controlled through their parameters

A component's internals are determined by the parameters it is constructed
with, its own state, and data it derives. Parents do not reach in and assign
child state (`day_glue.entries = ...` goes away).

This is expressed with the existing `Glue.attr`, not a new declaration type:

- **Identity attributes** (`identity=True`) are required parameters: everything
  needed to rebuild the component. `identity=True` already signs the value into
  the policy; what changes is that `_reconstruct_from_policy` becomes derivable
  (`cls(**policy.identity)`) and checkable at import time rather than
  hand-written and unvalidated.
- **Optional parameters** (`parameter=True`) are values a parent may pass so the
  component can skip work it would otherwise do. They are not signed and are
  never needed for reconstruction; when absent, the component derives them.
- **Every other attribute is internal.** A parent cannot set it.

```python
class TimeEntryDay(ComponentGlue):
    template = 'time_tracker/component/day.html'

    date        = Glue.attr(identity=True)                          # required parameter
    user_id     = Glue.attr(identity=True)                          # required parameter
    entries     = Glue.attr([], glue_factory=_build_time_entry_glue,
                            parameter=True)                         # optional parameter
    total_hours = Glue.attr(0.0)                                    # internal

    @entries.derive
    def _derive_entries(self):
        return TimeEntry.objects.filter(user_id=self.user_id, period=self.date)
```

`TimeEntryDayGlue` already declares `date = Glue.attr(identity=True)` and
`entries = Glue.attr([], glue_factory=...)`; the model adds `parameter=True`
and a derivation. The hook's exact form is not settled (`default` is
unavailable as a name: it is already a data attribute on `DeclaredAttribute`).
Writing `identity=True, parameter=True` together is redundant but allowed.

On week load the dashboard fetches every entry once and passes each day its
entries. When one day changes, that day reloads itself from its identity
attributes with a single scoped query.

#### The parameter contract

Parameters are the only way in, from a template or from Python. The
constructor is generated from the declarations, so the hand-written `__init__`
that `TimeEntryDashboardGlue` carries today goes away.

```python
TimeEntryDay(date=d, user_id=5)                  # ok; entries derived
TimeEntryDay(date=d, user_id=5, entries=rows)    # ok; entries supplied
TimeEntryDay(date=d, user_id=5, total_hours=8)   # error: not a parameter
TimeEntryDay(date=d)                             # error: requires 'user_id'
```

Reconstruction follows the same contract: `cls(**policy.identity)` passes only
identity attributes, so optional parameters are absent and derived.

**An optional parameter is only legal if the component can produce the same
value from its identity attributes.** Every input that shapes the derivation
must be an identity attribute; otherwise parent-supplied and self-derived data
diverge after the first mutation.

For a component, `identity` therefore means exactly its required parameters.
The built-in glue classes use `identity` for identifying input (`target_pk`),
configuration (`batch_size`), and signed mutable state (`loaded_row_count`)
alike; components do not inherit that ambiguity.

### 5. Components are stamped from templates and keyed at the render site

A template tag instantiates a component against its parameters at render time:

```django
{% for date, entries in component.week %}
    {% glue_component "time_tracker.TimeEntryDay" date=date user_id=component.user_id entries=entries key=date %}
{% endfor %}
```

The tag enforces the parameter contract. When the component path is a string
literal, its compile function can check argument names when the template is
parsed, before any request data is involved.

The tag **must establish parentage from the render context** — reading the
enclosing component that `get_context_data()` placed there — so stamped
components join the address tree rather than a flat namespace.

#### Keys

A key identifies a child among its siblings and **is chosen where the child is
rendered**, not declared by the component, as with Blazor's `@key` and React's
`key`. Uniqueness only means something relative to a parent: the same
`TimeEntryDay` is unique by `date` under a single-user dashboard and by
`(user_id, date)` under a team grid.

```django
{% for user in component.users %}{% for date in component.dates %}
    {% glue_component "time_tracker.TimeEntryDay" date=date user_id=user.id key=user.id,date %}
{% endfor %}{% endfor %}
```

- In Python, a collection attribute declares the key for its items —
  `entries = Glue.attr([], glue_factory=..., key=lambda entry: entry.pk)` — so
  it is still the list choosing, not the item.
- Client-side stamping uses `x-for`'s `:key`.
- The key is baked into the child's address at stamp time, and the address is
  signed as the policy name, so a key survives reconstruction without being an
  identity attribute.
- A key must stay the same for the same logical child across renders. A loop
  index is never a key.

An address is a path whose segments are unique only among siblings:
`dashboard.day_collection[2026-09-09].entries[471]`. A component with no
siblings — a single named child, or a root that appears once on a page — needs
no key and is addressed by name.

Because stamping happens on the server, missing and bad keys fail loudly rather
than degrading to positional matching, which is Blazor's behaviour without
`@key` and the bug the morph spike measured:

- Stamping inside `{% for %}` without `key=` is an error; the tag detects
  `forloop` in the context.
- Two children with the same key under one parent in one render is an error.
- `forloop.counter` or `forloop.counter0` as a key is an error at parse time.

#### Composition mechanisms

Two are kept, for different jobs:

- **Named child** — a fixed, single child (`entry.form`), as a nested policy
  at a dotted name. This is correct today.
- **Keyed collection** — dynamic membership, add/remove/reorder, as a manifest
  array keyed by the collection's key rather than array index (`SequenceGlue`
  currently names items `f'{name}.{index}'`).

With Alpine as a dependency, components can also be stamped client-side inside
`x-for :key`, which is the path for reorderable collections (see §6).

### 6. Replaced HTML is morphed with Alpine.morph

Server-rendered HTML that replaces existing content is always applied with
`Alpine.morph`; glue never replaces DOM any other way. Insertion
(`renderInsertAdjacentHtml*`) stays plain insertion, and state changes reach
the DOM through Alpine's bindings without glue writing nodes. Morph boundaries
are component boundaries, and addresses supply the node keys.

- A component template has a **single root element**.
- Subtrees owned by third-party JavaScript (ECharts, flatpickr, Bootstrap
  widgets) opt out with an ignore attribute.
- Wholesale reorder of a collection goes through keyed `x-for`, not server
  re-render, because morphing does not reliably relocate nodes on a full
  reversal.

## Evidence: Morph Spike

`django_glue/tests/e2e/test_lab_morph.py` against
`test_project/lab/views/morph_views.py` (`/lab/morph/`). A region of four
cards, each with a stable `id` and `key`, local Alpine state, a text input,
and one card with a subtree written by imperative JavaScript. Re-rendered
server HTML is applied under three strategies. The verified run is 13 passed,
10 failed; every failure is a replace or idiomorph case except Alpine.morph's
full reorder.

| | replace (current) | idiomorph | Alpine.morph |
|---|---|---|---|
| Server content lands | pass | pass | pass |
| Local Alpine state survives | fail | fail — DOM desync | pass |
| `init()` not re-run | fail | pass | pass |
| Focus and caret survive | fail | fail | pass |
| Nodes relocate on full reorder | fail — rebuilds all | pass — exact¹ | partial (2 of 4) |
| Dropping a card leaves siblings intact | fail | fail — DOM desync | pass |
| Ignore attribute protects third-party DOM | n/a | pass | pass |

¹ Relocation is exact, but `test_state_follows_card_across_reorder[idiomorph]`
still fails: once the nodes move, the relocated card's rendered state desyncs
exactly as in the state rows above.

Findings:

- **Replacement fails every preservation case** and rebuilds every node on
  reorder.
- **idiomorph is silently wrong with Alpine.** It preserves nodes and Alpine
  scope objects, then patches rendered output back to the raw server HTML.
  Alpine does not re-run its effects because its state did not change: the
  scope holds `counter: 2` while the DOM is empty, and `x-show` panels lose
  `display: none`. This is why a framework-agnostic morph default was
  rejected rather than merely ranked lower.
- **Alpine.morph passes everything except full reorder**, where its keyed
  lookahead relocated two cards and rebuilt two. That case belongs to keyed
  `x-for` (§5, §6).
- **Stable ids drive exact relocation.** idiomorph's perfect reorder came from
  `id` matching, which canonical addresses provide.

## Consequences

- **Supersedes `docs/roadmap/proxy_instance_management.md`.** Per-access
  proxy construction existed so proxies were built after Alpine's `initTree`.
  Glue can now make state reactive itself, but only once Alpine has loaded:
  glue currently initialises during parsing, before Alpine's deferred script
  runs, so start-up order has to be handled (see Open Questions).
  The decision's second objection — that a singleton makes cross-scope
  coupling the default — applied to a global accessor, not to a mounted
  component tree. GLUE-93 is expected to disappear rather than be fixed. The
  singleton registry and `reactiveSelf()` removed in `b36df60` are recoverable
  from history.
- **`AGENTS.md` layering rules change.** The framework-independence rule is
  retired. *"`GlueClient` stays namespace-agnostic"* and *"proxy-specific
  behavior lives on the proxy class"* are unaffected and remain in force.
- **`docs/roadmap/adapter_refactor.md`** describes Glue as *"a general Python
  object proxying system."* That remains true of the Python side; the client
  is now Alpine-specific. The roadmap should say so.
- **The three HTML envelopes must unify** (`GlueTemplateResponse`,
  `GlueViewFragmentResolver`'s bare `{html, manifest_list}`, and
  `TemplateGlue.render_html`'s `{html}`), because morphing needs one patch
  path. This was already a TODO in `django_glue/response.py`.
- **`takes_client_state` / `updates_client_state` become load-bearing.** Under
  self-sufficient derivation, refreshing state may re-derive from the
  database, so these flags decide between one query and many. Their naming and
  defaults need revisiting before components depend on them.
- **Stale documentation.** `AGENTS.md` still documents the removed
  `proxies/` package, `@action`, and session-based registration, and
  `docs/architecture.md` is partially stale on signing and expiry.

## Open Questions

- **Instance semantics (C1).** Recommended: restore a registry of stable,
  reactive instances. Needs a decision on what replaces the four identity
  tests and how held references observe `loadManifests()`.
- **Start-up order.** `{% django_glue_init %}` constructs `GlueClient` inline
  during parsing while Alpine loads with `defer`, so Alpine is undefined when
  manifests load. Options: make instances reactive on `alpine:init` or first
  access; delay glue's start-up until Alpine loads (breaks inline scripts that
  use `Glue` during parsing, such as the `Glue.onMessage` setup); or bundle
  Alpine so glue controls the order.
- **Alpine packaging.** Recommended: peer dependency — expected on the page,
  not bundled.
- **Parent reaction.** Proposed: a child's policy carries its ancestor chain
  so the server can reconstruct upward and run a parent handler in the same
  round trip, returning addressed state for several components. The same
  multi-component response shape is what targeted invalidation needs.
- **Signed mutable state.** `QuerySetGlue`'s `loaded_row_count` and
  `last_query_params` are signed but change every request, so they are
  neither parameters nor state. Where they live is unresolved.
- **Cascading parameters** (Blazor `[CascadingParameter]`) to avoid threading
  values such as `user_id` through every level.
- **Client-only state** for ephemeral UI values (`isProcessing`, `open`) and
  whether Alpine owns it natively or components declare it.
- **Lifecycle**: mount/hydrated signal, re-derivation when inputs change
  (Blazor `OnParametersSet`), and disposal of a stamped child whose parent
  re-renders without it.
- **Transient children** — a first-class unplaced child for modal forms,
  replacing the manifest-splatting in `TimeEntryDayGlue._build_time_entry_payload`.
- **Targeted invalidation** replacing window events and full-week refetch.
- **Policy token size** as ancestor chains and identity attributes grow.
- **Parameter immutability.** Recommended: a component cannot reassign its own
  identity attributes. Doing so re-signs it with inputs that no longer match
  the key its parent stamped; Blazor likewise discourages components
  overwriting their own parameters.
- **Composite key syntax** at the render site (`key=user.id,date` is a
  placeholder).

## Rejected Alternatives

- **django-unicorn** — server-rendered diff on every interaction; round trips
  for trivial local state, and component state on the wire.
- **Tetra** — co-compiled Python and Alpine; an opaque transpile boundary.
- **django-components** — server-side composition with no state model.
- **Lit** — real client components, but the backend contract is left to the
  application, which is the part Glue already provides.
- **Housing the system in django-spire.** Spire cannot fix GLUE-93, the
  envelope split, or the identity model, all of which are glue internals.
  Passing template paths rather than definitions avoids the concern behind
  spire's modal ADR, which rejected glue owning presentation.
- **A framework-agnostic morph seam with an idiomorph default.** Measured to
  desync silently from Alpine state (see Evidence). Degrading to replacement
  would at least fail visibly, but became moot once Alpine was a dependency.
- **Render-first components**, where every interaction can return fresh HTML.
  Regresses the dashboard toward django-unicorn and multiplies payload for
  values state already carries.
- **Parent-held children only.** Keeping every child as a parent attribute
  prevents stamping components from templates.
- **Data as identity attributes.** Signs the page's data into every token and
  makes it stale by construction.
- **Scalar inputs with batched derivation (dataloader).** The most faithful to
  a single input concept, but requires invisible batching machinery; optional
  parameters solve the same query cost more simply.
- **Keys declared on the component (`key=True`).** Uniqueness is relative to
  the parent, so the same component needs different keys under different
  parents. Blazor and React both key at the render site.
- **A class-level default key with render-site override.** Avoids repeating
  the key, but keeps a list concern on the item and hides the choice from
  the render site where uniqueness is actually decided.
- **A separate `Glue.prop` / `Glue.data_prop` declaration.** Duplicates what
  `Glue.attr(identity=True)` already does and splits one established
  vocabulary in two; `parameter=True` makes the input contract explicit
  without it.
- **Other names for `parameter`.** `suppliable` read poorly; `input` shadows a
  builtin and trips ruff `A002` in glue's own signature; `init` inverts
  dataclasses' opt-out default and collides with Alpine's `init()`;
  `settable` is confusable with client-writable state; `optional` says a
  value is not required but not that it is accepted from outside.
