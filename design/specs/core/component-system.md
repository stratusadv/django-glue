# Component System

Status: Accepted living design; implemented on the django-glue state-model
branch. Portal consumer migration to that branch remains a separate gate.

Date: 2026-09-10

## Context

Django Glue began with signed, stateless policies, declared attributes, a
namespace registry, and server-authored HTML. The state-model refactor gives
those pieces addressed children and the flat `objects` response envelope.

The time-entry dashboard in stratusadv-portal first proved the ViewModel half
of a component system with a registered Glue object and `next_week()` command.
It now lives at `app/time_tracker/components/time_entry_dashboard.py` and is
stamped by the portal dashboard page. Its browser E2Es cover keyed week
navigation and the add-entry modal on the portal's component branch.

The original composition problems motivating this design were:

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
- Server-rendered HTML was applied by replacement (HTML results,
  `GlueView`, `GlueTemplateProxy`), which destroys Alpine scopes and local UI
  state.

Tetra, django-unicorn, django-components, and Lit were evaluated and rejected
(see Rejected Alternatives). References are split by concern, because the two
frameworks differ in the constraint that matters here.

**Blazor** is the reference for **composition**: parameters flowing down, events
flowing up, and keys chosen at the render site.

**Livewire** is the reference for **state and mechanism**: server-driven
components over Alpine with morphing, and how values survive a round trip.

The split is not stylistic. Blazor Server keeps a component alive in a stateful
circuit, so its answers assume private fields persist between interactions. Glue
rebuilds from a signed token on every request and has no circuit — so where
Blazor says "hold it in a private field," glue would silently lose it. Livewire
is stateless per request exactly as glue is, which makes it the sound reference
wherever state crosses the wire. See [`state-model.md`](state-model.md).

## Decision

### 1. The component system lives in django-glue

Glue owns the component system end to end. Glue objects receive **template
paths only**; glue never holds template definitions, markup, or styling. That
keeps presentation with the consuming project and django-spire while Glue owns
only the rendering contract.

### 2. Alpine.js is a dependency of glue's client

Glue's JavaScript client may call `Alpine.reactive`, `Alpine.morph`,
`Alpine.data`, `Alpine.addScopeToNode`, and hook Alpine's lifecycle. The
Python side remains framework-free.

This retires the layering rule *"Glue core must not reference any frontend
framework."* Glue was already designed around Alpine — per-access proxy
construction, `_mergeState`, and GLUE-93 are all reasoned in Alpine's terms —
while being forbidden from using Alpine's affordances.

Glue bundles Alpine and its morph plugin at matching, pinned versions (currently
3.15.12). `client_js/src/alpine.js` is the only client module that references
`Alpine`. Consuming projects remove their separate Alpine core and morph
scripts. Optional plugins remain project-owned and register against
`window.Alpine`, the runtime exposed by Glue.

`{% django_glue_init %}` exposes Alpine and constructs `GlueClient` during page
parsing. Glue starts Alpine at `DOMContentLoaded`, after deferred plugin scripts
have registered. Existing `alpine:init` handlers run before the DOM mounts;
inline `Glue.onMessage` setup remains synchronous. Glue objects can already be
used during parsing: `Alpine.reactive(instance)` does not require DOM startup.
Alpine returns the same proxy for the same object, so each registered name resolves to one live instance
(`Glue.model.gorilla === Glue.model.gorilla`), and `loadManifests()` patches
that instance in place, so references held in `x-data` observe re-rendered
state. Loading another Alpine core runtime is an installation error; Glue
detects an existing runtime at installation and a replaced runtime at startup.

Application-specific client-only UI state belongs directly to Alpine. Values
such as `open`, `activeTab`, hover state, and temporary widget state are
declared in `x-data`; components do not duplicate them as Python declarations
or place them in policy tokens. They survive while their Alpine scope survives
the morph and reset when that scope is intentionally destroyed.

Glue's client separately owns transport state such as whether an address or
trigger is loading, has a pending call, or encountered a transport error. It
may expose that state to Alpine through client-side bindings, but it is runtime
metadata rather than component state and never participates in server
reconstruction. A value becomes Glue state only when the server owns it or
will consume it on a later request. A one-off local value may instead be passed
as an untrusted callable argument and validated normally.

### 3. A component is a `BaseGlue` subclass that owns a template path

```python
class TimeEntryDay(Glue.Component):
    template = 'time_tracker/component/day.html'
```

- The template path is declared on the class, with a constructor override.
- The render context comes from `get_context_data()`, which by default
  exposes the component instance.
- **Rendering is state-first.** A component is server-rendered at mount.
  Steady-state updates flow through state and Alpine bindings, exactly as the
  dashboard works today. `render()` exists for mount and for dynamic insertion
  (modals, fragments, and structural change such as a new week).
- **State synchronization is not rendering.** Responses carry a successor
  policy token and addressed `computed_data` as defined by `state-model.md` §5
  and §10. The client assembles and reconciles their values into the existing
  reactive object; it does not replace the object or infer data from rendered
  HTML.
- **Components do not introduce a state engine.** They use the same signed
  parameters and state snapshots, editable-update admission and domain
  validation, unsigned response data, effects, and client reconciliation as
  `ModelGlue`, `FormGlue`, `QuerySetGlue`, and the other existing families.
  Component behavior is a composition layer over `BaseGlue`, not a replacement
  for its established entrypoints.
- **Calls are ordered per address.** The client advances one component's token
  and canonical data before sending its next call, while unrelated component
  addresses may proceed concurrently. Cross-tab freshness is supplied by the
  state model's opt-in authoritative version contract, not by component
  instance semantics.
- **Call arguments use the shared capability pipeline.** A component method's
  signed capability positively lists its client-supplied arguments. Parameters
  classified as server-injected from the current annotation are excluded, and
  a client collision is rejected before the method runs.

### 4. Components are closed systems controlled through their parameters

A component's internals are determined by the parameters it is constructed
with, its own state, and data it derives. Parents do not reach in and assign
child state (`day_glue.entries = ...` goes away).

The state roles, construction exposure, and their transport are owned by
`state-model.md`; the component boundary gives them their composition meaning:

- `Glue.attr(parameter=True)` is a reconstructor supplied from outside the
  component and accepted by its generated constructor;
- `Glue.attr(x)` is an internal reconstructor and is not a parent input;
- `Glue.attr(x, parameter=True, editable=True)` is editable state that can be
  supplied at construction and subsequently updated through its admitted,
  untrusted client channel;
- `Glue.attr(x, editable=True)` is internal draft state whose client updates
  are admitted against its signed canonical baseline and revalidated before
  domain use; and
- `@Glue.property` is derived output, recomputed rather than accepted from a
  parent or hydrated from the client.

`parameter=True` is not a role. It independently exposes either a reconstructor
or editable-state declaration to initial construction. `editable=True` selects
the editable-state role; omitting it selects the reconstructor role.

`identity=True` and the earlier optional-parameter category are removed. The
signed policy token's `target.parameters`, `state_snapshot`, and shallow
`children` map give the framework everything it will consume on the next
request without treating derived output, child policy, or schema as component
memory.

```python
class TimeEntryDay(Glue.Component):
    template = 'time_tracker/component/day.html'

    date: datetime.date = Glue.attr(parameter=True)
    user_id: int = Glue.attr(parameter=True)
    note: str = Glue.attr('', parameter=True, editable=True)

    @cached_property
    def _entries(self):
        return TimeEntry.objects.filter(user_id=self.user_id, period=self.date)

    @Glue.property
    def total_hours(self):
        return sum(entry.allocated_hours for entry in self._entries)
```

#### The parameter contract

Parameters are the only way in, from a template or from Python. The
constructor is generated from the declarations, so the hand-written `__init__`
that `TimeEntryDashboardGlue` carries today goes away.

```python
TimeEntryDay(date=d, user_id=5)                # ok
TimeEntryDay(date=d, user_id=5, note='draft')  # ok: editable parameter
TimeEntryDay(date=d, user_id=5, total_hours=8) # error: not a parameter
TimeEntryDay(date=d)                           # error: requires 'user_id'
```

Parameter delivery is explicit and non-reactive by default, following
Livewire's independent-island model. A template or Python construction site
names every supplied parameter. Intermediate components must forward a value
when a deeper child requires it; descendants do not search their ancestor tree
for an ambient provider. Moving a component therefore cannot silently change
which provider satisfies its construction contract.

Once stamped, a child owns its signed parameter value. A later change to the
expression that originally supplied it does not automatically update the
already-mounted child. A future explicit reactive-parameter binding may
selectively batch the independently signed parent and child entries, but ordinary
parameters create no subscription or implicit whole-subtree invalidation.

Request-scoped dependencies such as the current request, authenticated user,
and server services use Glue's server-injection path rather than masquerading
as component parameters. An identifier such as `employee_id` remains a
parameter when it genuinely selects what object the child represents.

#### Properties may declare configured Glue-object children

A typed `@Glue.property` on any addressed Glue object may return a configured
`BaseGlue` object. Plain property values remain down-only derived data; a
declared Glue-object result instead defines a stable named child relationship
and is encoded as a reference to that child's address. Components use this for
composition, but the same mechanism lets a `ModelGlue` expose a configured
form, a custom object expose a queryset, or any other Glue family introduce an
addressed child without rendering HTML:

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

The non-registering `Glue.model`, `Glue.form`, `Glue.queryset`, and
`Glue.formset` shortcut forms are the public construction path. A custom
`BaseGlue` is constructed directly. The existing
`Glue.object(request, glue)` shortcut only registers an already-configured page
root; it does not construct a child. Returning the raw Django object is an
error because no field, operation, query, or access capability has been
configured.

The return annotation is part of the declaration: it compiles the child slot,
expected Glue family, and nullability into schema. Glue requires the runtime
result to match. An unannotated `@Glue.property` remains ordinary derived data
and fails loudly if it unexpectedly returns `BaseGlue`; a normal Python
`@property` remains entirely server-internal.

The component owns the relationship and the child lifecycle, not the child's
state. `chat-panel.chats` has its own policy, state snapshot, request queue, and
reconciliation. A later component response may repeat the stable reference but
must not replace or advance an already-live child's independently evolved
policy or editable draft. Component disposal recursively disposes the child.

Nesting creates no implicit reactive dependency. Alpine may bind directly to
the child proxy for immediate UI reactivity. After a persisted child mutation,
composition code may explicitly await `component.$refresh()` or subscribe to a
declared child event and refresh. If retained component state must change, it
does so through an explicit component callable. If the child mutation and
component transition must be atomic, one component callable owns the complete
operation. Glue never copies child draft state into the parent or automatically
refreshes an owner on every child update.

#### Mount

`mount()` is the single initial-introduction hook for a component. Glue calls
it after the generated constructor has assigned declared parameters and state
defaults, and after the component has been bound to the current request, but
before issuing its first policy token and rendering its initial HTML.

```python
class EntryEditor(Glue.Component):
    entry_id: int = Glue.attr(parameter=True)
    draft_title: str = Glue.attr('')

    def mount(self):
        self.draft_title = Entry.objects.values_list('title', flat=True).get(
            pk=self.entry_id,
        )
```

Glue does not call `mount()` when reconstructing an object from a verified
token, advancing its token after an action, or rendering a parent that retains
the already-mounted child. It runs again only when a component is genuinely
introduced again: after removal, on a new page load, or when an expired child
is reintroduced through its owner (`state-model.md` §10). Consequently it is
suitable for producing initial retained state, but not for exactly-once durable
side effects: browsers can reload and initial responses can be retried.

Reintroduction reruns the factory and authorizes the result from scratch, so it
also reruns `mount()`: retained state the client cannot edit restarts from
`mount()`'s output, while the client's editable draft, Alpine scope, and
request queue survive at the same address and the draft is resubmitted as
ordinary `updates`. Recovering retained state from the expired token instead
would honor a token past its fixed lifetime (ADR 013). Livewire makes the same
trade at its equivalent boundary: its snapshot carries no expiry, its only
time bound is the session, and a 419 "page expired" ends in a reload that
remounts every component; reintroduction is the narrower form of that reload.

Introduction is one framework step for every Glue family, not a component
special case: `introduce(request)` authorizes the `introduce` operation and
binds the object to the request, and `Component` extends it by calling
`mount()`. Page roots, child slots, callable results, and reintroduced
children all introduce through it. A denied page root is an error, a denied
callable result fails its entry with `not_authorized`, and a denied child is
omitted and stays unbound.

The generated `__init__` remains framework-owned and may run during server
reconstruction. Glue does not bypass normal Python construction with
`__new__`, and developer code does not use `__init__` as a hidden mount hook.
Database-derived values that need no retained continuity remain
`@Glue.property` rather than being copied into state by `mount()`.

#### Hydration is framework-owned

Components expose no public `hydrate()`, `dehydrate()`, or per-request `boot()`
hook. On every interaction Glue verifies the token, reconstructs the target
from signed parameters, consults `authorize()`, restores `state_snapshot`,
admits editable updates, consults `authorize()` again for the attribute being
invoked, invokes the authorized callable, recomputes derived output, and issues
the successor token in a fixed order. Application code cannot interpose on that
security boundary.

`authorize()` is the one application-supplied step in that sequence and is not
an exception to the rule. It is a pure predicate: it answers yes or no, cannot
mutate the object, cannot observe or alter editable updates, and cannot change
the order around it. The rejected hooks were rejected for letting application
code *act* inside signed reconstruction; a predicate that can only decline is a
different thing.

Custom value representation belongs in the shared serializer registry rather
than lifecycle methods. Work needed for a specific interaction belongs in its
callable, while repeatable output remains a `@Glue.property`. These paths apply
equally to components and the established Glue-object families without giving
components a second reconstruction mechanism.

Request access has two complementary contracts, not one:

- **`self.request` is the bound-object contract.** Every `BaseGlue` is bound to
  the current request before `mount()`, before any property is derived, and
  before any callable runs. `@Glue.property`, `get_context_data()`, and adapter
  configuration read `self.request` directly — a property has no parameters to
  inject into, so this is the only available path and it is public API.
- **Server injection is the callable-argument contract.** A callable declares
  `request: HttpRequest` (or another registered injected type) and receives it as
  an argument that the client cannot supply or override. Injection exists to make
  a callable's dependencies visible in its signature and to close the
  client-collision hole, not to be the only way to reach the request.

Both resolve to the same request object. Neither is a lifecycle hook: reading the
request does not let application code interpose on reconstruction order, which is
what the rejected `hydrate()` / `boot()` hooks would have done. An unbound object
raises on `self.request` rather than returning `None`, so a configuration mistake
fails at the point of use.

Reconstruction supplies every parameterized value through the same constructor
contract, then restores non-parameterized reconstructors and editable drafts
from the verified token's `state_snapshot`. Editable updates are admitted only
for declarations in the editable-state role, whether or not they are also
parameters. A canonical editable draft may still be invalid for an action;
signing establishes continuity, not domain validity. Derived properties are
evaluated from that state and current authoritative sources. A component may
advance any of its retained values; the client may advance only editable state.

Shared derivation follows ownership rather than transport. Work that must be
coherent or memoized together stays on one addressed object and uses ordinary
private Python memoization there; independently addressed children derive from
their own signed parameters. Template partials or keyed Alpine regions may
split presentation without inventing child authorities. The removed
optional-parameter mechanism and request batching are not cross-object caches.

### 5. Components are stamped with a Django template tag

The public composition syntax is the `{% glue_component %}` tag established on
the component workstream (commit `e6f204b`):

```django
{% load django_glue %}
{% for date in component.dates %}
    {% glue_component 'time-entry-day' date=date user_id=component.user_id key=date %}
{% endfor %}
```

The first positional expression resolves the registered component tag name.
Named expressions resolve through Django's `FilterExpression`, retaining Python
types without an HTML attribute parser. `key` and `access` are reserved; all
other named expressions must be declared parameters. The tag is self-closing in
Django template syntax; slots remain deferred. The tag lives in the existing
`django_glue` template library, so no custom `DjangoTemplates` backend, HTML
element scanner, or `<glue:... />` grammar is part of the target design.

The render context supplies the composing component. A stamp inside a Django
loop requires a stable explicit key; `forloop.counter` and
`forloop.counter0` are rejected. A key must be an immutable supported scalar
or non-empty tuple of those values, canonicalized with type information.
Duplicate target/key pairs under one parent fail. The key determines a stable
child address under the composing parent on the addressed wire, while the
component class's registered identifier determines reconstruction. Changing
the public tag name does not replace that signed identifier.

Server-resolved parameters are sampled at introduction and signed. There is no
implicit subscription to the expression that supplied one. The tag has no
Alpine-bound parameter spelling, no `lazy` or `defer` mount mode, and no
stamp-level event handlers: every stamped component mounts during the server
render that stamps it, and event handling belongs on ordinary markup or on the
source proxy (see "Declared events communicate semantic outcomes"). Client-
evaluated parameters and delayed mounting would each need their own design;
neither is part of this one.

#### Tag names

`TimeEntryDay` derives the default tag name `time-entry-day`. A component may
override it when a shorter, domain-qualified, or collision-free public name is
needed:

```python
class TimeEntryDay(Glue.Component):
    tag_name = 'time-tracker.time-entry-day'
```

```django
{% glue_component 'time-tracker.time-entry-day' date=date user_id=user.pk key=date %}
```

Names are lowercase kebab-case segments separated by dots. Component
registration rejects two classes with the same effective tag name during
Django's startup checks rather than choosing by import order. The override
changes the public template name; it does not replace the component's signed
reconstruction identifier. Components are discovered from each installed
app's `components` module or package at startup.

The tag supports only registered components with a single root element.
Slots, paired tags, and dynamic component-class selection are separate
extensions.

#### Components as URL views

A component class may be the target of a Django URL pattern:

```python
path('cards/<int:start>/', CounterCard.as_view(), name='card-fragment')
path('cards/<int:start>/page/', CounterCard.as_view(
    template='gorilla/page/card.html',
), name='card-page')
```

`as_view()` serves safe HTTP requests through Django's ordinary URL and
middleware path. Named URL captures supply declared component parameters;
constructor defaults passed to `as_view()` supply parameters not captured by
the route. A component may override `get_view_kwargs(request, **url_kwargs)`
to return constructor kwargs derived from the current request, including a
request-specific `access` ceiling. The default returns the supplied kwargs.
The component is introduced and mounted once before rendering, with
the same signed root address and child entries as a template-tag stamp. Unknown
or missing parameters retain the component's normal constructor errors.

Without `template=`, the response is the component's declared template as an
HTML fragment, including its addressed root. With `template=`, the component
still renders its declared template first; the override is a page template
that receives `component_html` as safe rendered markup alongside the
component's normal context. A page template includes `{% django_glue_init %}`
to boot the client. Keeping the component template unchanged ensures later
`render()` calls return the same component fragment rather than a whole page.
Either route remains compatible with `Glue.view` content negotiation and its
ordinary middleware checks.

Django view decorators may guard the URL, as with any other view. That guard
applies to page retrieval; later addressed component calls use their own
endpoint. The component's `access=` value caps the signed operations, while
`authorize(request, operation)` enforces current application permission at
introduction and on later calls. An `authorize()` denial during direct URL
rendering becomes Django's HTTP 403 response.

#### Keys

A key identifies a child among its siblings and **is chosen where the child is
rendered**, not declared by the component, as with Blazor's `@key` and React's
`key`. Uniqueness only means something relative to a parent: the same
`TimeEntryDay` is unique by `date` under a single-user dashboard and by
`(user_id, date)` under a team grid.

```django
{% for cell in component.cells %}
    {% glue_component 'time-entry-day' date=cell.date user_id=cell.user_id key=cell.key %}
{% endfor %}
```

`key=` is an ordinary Django filter expression, and its resolved Python value
is the key: the scalar type survives, and a composite key is a tuple the
render context supplies (here `cell.key` is `(user_id, date)`). Django's
template language has no tuple literal, so composite keys come from the
context rather than from a key grammar; literal scalar keys remain available
for fixed variants.

- In Python, an addressed collection adapter declares the key for its items,
  so it is still the collection choosing, not the item. Querysets and formsets
  provide their own keyed addressed collections. A `Glue.attr(...)` list holds
  ordinary serializable data unless its items are meant to be proxies: a list
  holding Glue objects, or a declaration naming a `glue_factory` that turns
  raw items such as model instances into Glue objects, becomes an addressed
  `SequenceGlue`. A list mixing Glue objects with raw items and no factory is
  an error, never plain data.
- A server-authored stamp inside a Django loop supplies `key=`.
- The registered component target and canonical key are baked into the child's
  address at stamp time, and the address is signed as the policy name. The same
  key may be used by different child targets under one parent; two instances
  of the same target and key are the same logical child.
- Server-authored parameter changes do not change that address. For example, a
  form child keeps its temporary key when `target_pk` advances after creation;
  only a later parent render can explicitly replace it under another key.
- A key must stay the same for the same logical child across renders. A loop
  index is never a key.

Resolved keys must be immutable, key-safe scalar values supported by Glue's
serializer registry, or non-empty tuples of those values. Glue canonicalizes
the typed value rather than calling `str()`, so integer `1`, string `"1"`, and
composite `(1, "2")` cannot collide. Mutable containers, Glue objects, Django
models, forms, and querysets are not keys.

An address is a path whose segments are unique only among siblings. Its debug
form may look like `dashboard.TimeEntryDay[(184,2026-09-09)].entries[471]`;
the wire representation is opaque and never reparses that display spelling. A
component with no same-target sibling needs no explicit key. Multiple instances
of the same target under one parent require distinct keys even outside a loop.

Missing and bad keys fail loudly rather than degrading to positional matching:

- A server stamp rendered under a Django `forloop` without `key=` is an error.
- Duplicate target/key pairs under one parent are an error.
- A direct `forloop.counter` or `forloop.counter0` key is rejected.

#### Composition mechanisms

Three shapes are kept, for different jobs:

- **Callable namespace** — an explicit `Glue.namespace(...)` marker creates a
  stable dotted client path such as `user.services.processor.send()`. The complete
  callable path belongs to the owner's schema and capability and targets the
  owner's own policy; the intermediate namespace objects have no state, address,
  policy, or lifecycle. The marker wraps the ordinary class attribute a project
  already writes and forwards its descriptor untouched, so binding stays the
  provider's business and existing service declarations need no rewrite. A
  provider needing construction arguments is declared as an annotated function
  instead, the same "annotation declares, body produces" shape a child-producing
  `@Glue.property` uses. Either way it is declared wherever `@Glue.attr` attributes
  already are — on a Django model or queryset class, at the `Glue.model(...)`
  configuration boundary, or on a `BaseGlue` subclass. `Glue.attr(...)` remains
  state-and-callable only and cannot declare a namespace.
- **Named child** — a typed property on any addressed Glue object, or equivalent
  built-in adapter declaration, returns a configured Glue object at a fixed
  path such as `entry.form`. The introduced object has its own address, token,
  state, and lifecycle. The owner's signed `children` map carries its address,
  never its policy or state.
- **Keyed collection** — dynamic membership, add/remove/reorder, as an ordered
  stable-key list resolving independently addressed children rather
  than a positional manifest array (`SequenceGlue` currently names items
  `f'{name}.{index}'`). The canonical transport and admission rules are defined
  in `state-model.md` §8.

### 6. Replaced HTML is morphed with Alpine.morph

Server-rendered HTML that replaces existing content is always applied with
`Alpine.morph`; glue never replaces DOM any other way. Insertion
(`renderInsertAdjacentHtml*`) stays plain insertion, and state changes reach
the DOM through Alpine's bindings without glue writing nodes. Morph boundaries
are component boundaries, and addresses supply the node keys.

When a response contains both `computed_data` and HTML, the successor token and
`computed_data` are assembled and reconciled first, and the HTML is morphed
second. The state model preserves editable values changed after the request was
sent; morphing preserves the corresponding DOM nodes, Alpine scopes, focus, and
caret. Neither mechanism substitutes for the other.

- A component template has a **single root element**.
- Subtrees owned by third-party JavaScript (ECharts, flatpickr, Bootstrap
  widgets) opt out with an ignore attribute.
- Wholesale reorder of a collection goes through keyed `x-for`, not server
  re-render, because morphing does not reliably relocate nodes on a full
  reversal.

### 7. Glue objects are independent addressed islands

Every addressed Glue object owns the policy token for its own canonical address. A child
token does not embed its parent's token, ancestor state, or sibling state, and
a parent token does not embed child policies. An owner token carries only a
shallow signed `children` map from canonical paths to addresses, allowing the
client to preserve, replace, or remove relationships authoritatively. The
independently addressed children still own their own policies and state
snapshots.

This follows Livewire's useful boundary: nested components are independent
islands, ordinary interactions submit only the target snapshot, and reactive
parent/child work selectively bundles independent component messages. Glue
generalizes that boundary from UI components to every addressed Glue object.

This is the shared Glue-object transport contract, not a component-only state
mechanism. A component, `ModelGlue`, `FormGlue`, `QuerySetGlue`, `FormSetGlue`,
`SequenceGlue`, `FunctionGlue`, or custom `BaseGlue` object is one independently
addressed object. Nesting affects composition and client lookup, not ownership of
the signed state. Leaves such as form fields remain part of their owning
object’s token unless they are themselves exposed as nested Glue objects.

The same composition path therefore applies when no UI component participates.
A `ModelGlue` may introduce a configured `FormGlue` at `model.form`; a
`QuerySetGlue` may introduce keyed `ModelGlue` rows; a `FormSetGlue` may
introduce keyed `FormGlue` objects; and a custom `BaseGlue` may return any
configured Glue family from a typed `@Glue.property`. Components add HTML rendering and
mount lifecycle, not a privileged object-composition mechanism.

Client syntax remains intentionally fluent across the boundary. For example,
`model.services.increment_age()` may call the complete namespaced attribute
`services.increment_age` through the model token, while `model.form.save()`
calls the local attribute `save` through the child form token. The object-graph
facade hides that routing distinction but never merges the two capabilities.
The server-side attribute registry, signed child references, and client address
registry—not dotted spelling—determine the target.

The default interaction sends only the target object's address, token, updates,
and optional call. Parent calls initiated from a child are addressed to the
already-mounted parent proxy and use the parent's token directly; the child
does not grant or reconstruct parent authority. Likewise, a queryset operation
uses the queryset's token, while an operation on an independently introduced
row or form uses that object's token.

When an interaction genuinely affects several addressed objects, the client
may batch their independent request entries in one HTTP request and the server
returns one successor entry per affected address. This supports independent
refreshes and established Glue-family composition without an ancestor-token
stack. Each token is verified against its own target and current authorization.
Batching changes transport coordination only; it does not merge capabilities,
state snapshots, proxy identities, request queues, or causal histories.

A child save followed by a parent refresh is therefore two causally ordered
requests. The child result or declared event may tell composition code to issue
`parent.$refresh()` with the parent's own token after the save response is
applied. Merely placing both operations in one batch does not guarantee that
the refresh observes the save. If the transition must be atomic, one
authorized callable owns the complete operation. The server neither discovers
the client dependency graph nor manufactures parent authority from the child
token.

#### Refresh is an addressed Glue-object operation

Every addressed Glue object exposes `$refresh()`. It sends an ordinary request
for that address with its current policy token and **no** editable updates, and
invokes no application callable. The server reconstructs and reauthorizes the
object through its normal adapter, recomputes its current downward output, issues
a successor token, and the client applies the ordinary three-way reconciliation.
Refresh is therefore shared by components, models, forms, querysets, formsets,
sequences, functions, and custom objects rather than being a component lifecycle
hook.

`$refresh({submit: true})` additionally admits the address's pending editable
updates before re-deriving. Keeping that opt-in is what makes refresh safe as the
polling primitive: a polled form must not push a half-typed draft on every tick
and have each response acknowledge it as canonical. The full contract is in
[`state-model.md`](state-model.md#6-effects-and-fragments-are-separate-channels).

The adapter determines what returning to its authoritative source means. A
model refetches and reauthorizes its row before reapplying its retained draft
overlay; a form reconstructs its bound form without discarding admitted raw
values; and a queryset reruns its query. A mounted component recomputes its
properties, renders its template, and morphs its root as part of `$refresh()`;
an unmounted component still returns the rendered HTML for a host to mount.
Application code does not invoke `render()` to reconcile a component after a
mutation. The reconciliation rules in `state-model.md` §5 preserve edits made
while the refresh is in flight. Refresh never means reset.

Glue does not attempt to infer a dependency graph from a model save. Arbitrary
query predicates and computed properties make that both incomplete and
surprising. Composition code names the live proxies whose views are now stale
and calls them directly:

```javascript
await entry.form.save()
await Promise.all([day.$refresh(), dashboard.$refresh()])
```

The client deduplicates refreshes by canonical address and queues each behind
that address's in-flight work. A missing or disposed target is ignored, and
independent refresh entries scheduled together may be selectively batched in one
HTTP exchange. There are no server-authored refresh targets, wildcard paths,
inferred ORM subscribers, or global window-event names in the initial
contract.

#### Declared events communicate semantic outcomes

Any addressed Glue object may declare a one-shot server-to-client event. The
declaration uses the same public shortcut style as other Glue features:

```python
class EntryEditor(Glue.Component):
    saved = Glue.event()

    def save(self):
        entry = save_entry(...)
        self.saved(pk=entry.pk)
        return entry.pk
```

Invoking the event descriptor does not dispatch globally or run application
code on the server. It appends a semantic event to the current successful
response entry's `effects.events`. Only declared events may be emitted; their
names appear in schema so component stamping and client subscription can reject
unknown names. Event detail accepts ordinary serializable output values. A
configured Glue object instead travels through the callable `result` channel,
where its address and lifecycle ownership are defined.

Because a rendered component bridges its declared events to real bubbling DOM
events, event names are constrained in two ways:

- **Names that collide with standard DOM events are rejected at schema
  compilation.** A component declaring `change`, `input`, `submit`, `error`,
  `click`, `load` or any other event in the standard set would dispatch something
  indistinguishable from the native event to every ancestor listener on the page,
  including third-party widget code and spire's own form handling. The check runs
  against a published list at startup, alongside the duplicate-tag-name check, so
  the failure is a registration error rather than a runtime surprise.
- **Every bridged event carries its source address.** The `CustomEvent`'s
  `detail` includes a reserved `$address` alongside the declared detail, and the
  event also exposes the source proxy directly. An ancestor `@saved` listener
  filters on that address rather than on node identity, because a component's
  root element can be replaced by a morph while its address is stable — filtering
  on `event.target` would break exactly when the design's morph-preservation
  guarantees are doing their job. The reserved key is documented and rejected as a
  declared detail name.

The `{% glue_component %}` tag accepts typed parameters, `key`, and `access`.
It does not parse Alpine event handlers. A composing template may listen for a
child's bubbling DOM event on ordinary markup, or application code may subscribe
to the exact child proxy with `$on()`. The event detail carries the source
address so a DOM listener can filter multiple children under one ancestor.

The event source is the response entry's canonical address and active client
generation. Every Glue proxy provides a source-scoped listener independent of
whether it renders HTML:

```javascript
const stop = entryEditor.$on('saved', event => {
    console.log(event.detail.pk)
    dashboard.$refresh()
})
```

`$on()` returns an unsubscribe function and source disposal removes all of its
listeners. A rendered component additionally dispatches a real bubbling
`CustomEvent` with the same name and detail from its current root. This is the
Alpine-facing delivery path: `@saved`, `x-on:saved`, `$event.detail`, `.once`,
`.stop`, and an explicitly chosen `.window` listener retain their ordinary
browser meanings. Glue does not maintain a second global event bus or dispatch
directly to a named component.

A source-scoped `$on()` handler is bound to the exact child's source even when a
descendant emits an event with the same name. An owner may explicitly expose one
owned child's declared event under its own public event name, for example
`saved = Glue.event(from_child='entry.form.saved')`. This declaration adds a
subscription on the owner for that exact descendant path and event; other child
events remain private. Delivery retains the form as `event.source` and the
original `$address`, while `event.currentTarget` is the exposing owner. A
mounted owner bridges this exposed event from its root as one bubbling DOM
event. The owner cannot emit a forwarded event directly from server code.
General ancestor DOM listeners receive normal bubbling semantics and may
inspect the address in event detail.
A model, form, queryset, or other
non-rendered Glue object has no canonical DOM root and therefore exposes the
same event only through `$on()`. The source-scoped proxy event is the universal
contract; the component DOM event is its browser integration.

Components expose their DOM relationship without requiring a global string
name. Within a component template Alpine's `$glue` magic resolves the current
component proxy. Plain JavaScript can resolve the nearest component from an
element and then use the same proxy API:

```javascript
const editor = Glue.from(document.querySelector('#entry-editor'))
editor.$on('saved', event => console.log(event.detail.pk))
await editor.save()
```

`component.$el` returns its current root, while `Glue.from(element)` walks to
the nearest addressed component root. Root association follows the component
address across morphs, and both lookup forms fail after disposal rather than
returning a stale incarnation.

Events are delivered after the complete originating response has been applied,
so a handler observes the successor state, introduced result objects, and any
completed morph. A handler that calls or refreshes another Glue object uses
that object's own token. If the response fails, queued events are discarded;
if the response is lost, they are not retried as durable messages.

Client code can construct a browser event with the same name, so observing a
DOM event is never proof that a server action succeeded. This does not weaken
server authority: any callable reached by an event handler still admits and
validates its arguments and checks its own policy. Glue event declarations
control what the server may emit, not what JavaScript may do within its own
page.

This does not preserve the old `before` / `after` / `error` listener system.
Those hooks observe client transport by callable name and have no consumers;
declared events are semantic outputs chosen by server code. Built-in adapters
may declare documented events where the meaning is unambiguous—for example a
successful form or model `saved` event—but Glue does not synthesize an event
from every callable name or validation failure.

#### Shared derivation follows ownership

Request batching and shared derivation are separate concerns. Batching reduces
HTTP overhead; it does not create a cross-address evaluation context, pass a
parent's derived output into a child, or make one object's result depend on
whether another unit happened to share its request. Every bundled unit must
reconstruct and derive the same result it would have produced alone.

The rule is **compute together, own together**. When several displayed regions
require one coherent or expensive read, one addressed Glue object owns that
read and exposes the resulting values through several `@Glue.property`
declarations. A private `cached_property` shares the work within that Python
object for the current request. Template partials and keyed Alpine regions may
divide its presentation without becoming independent components merely because
they are visually separate.

Applied to the time-entry dashboard, the dashboard owns `user_id` and
`week_of`, constructs one cached `TimeEntryPeriod`, and derives both the weekly
summary and keyed day data from it. Day cards are presentation regions unless
they genuinely need independent server state or lifecycle. Creating a form can
remain an authorized dashboard callable that accepts a date and returns a
configured transient `ModelGlue`. After save, one `dashboard.$refresh()`
recomputes the coherent week rather than separately querying a dashboard and a
day component.

An independently addressed child instead receives the minimum signed
parameters needed to reconstruct itself and performs its own derivation. That
independence has a real cost and should be chosen for independent interaction,
lifecycle, or loading—not as a template-partial mechanism. If unrelated
addresses need application-wide caching, they use an ordinary application
service or Django cache with explicit freshness semantics. Glue does not add a
request-scoped `derive`, provider, or cross-object memo API whose behavior
would change when the client bundles requests.

The signed `children` map records semantic ownership and lifecycle. DOM-node
associations remain local client-registry bookkeeping and never enter the
policy. Collection membership or order that the server consumes separately
continues to follow the state model's signing test.

#### Disposal follows address ownership

Disposal is a client lifecycle, not a Python component hook. Every live address
has exactly one lifecycle owner: the page owns top-level Glue objects, and an
addressed object owns each nested object it introduces. JavaScript references
to a proxy do not become owners. Introducing one already-live address under a
different owner is an error.

An address is disposed when its component root is removed during a morph, its
owner authoritatively removes it from a keyed collection or successor
`children` map, an `effects.dispose` entry removes a nonvisual object, or the
page unloads. Disposal recursively removes the addresses that object owns,
including transient callable results, whose ownership the client registry records
at registration rather than reading from a signed map. This ownership
contract applies to components, forms, models, querysets, formsets, sequences,
functions, and custom Glue objects; only components additionally own DOM and
Alpine cleanup.

Each client registry entry carries a local, monotonically increasing
generation for that address. A request captures the registry entry and its
generation. Its response entry is applied only if that exact generation is
still active. Disposal cancels queued calls, aborts a single-address in-flight
request where possible, runs Alpine and registered client cleanup, recursively
disposes owned addresses, and removes the entry from the active registry. A
shared batched request is not aborted; response entries for disposed generations
are discarded individually.

Existing references to the disposed proxy become tombstones and reject later
calls rather than silently targeting a future object. Reintroducing the same
canonical address creates a new proxy generation and calls `mount()` again.
This prevents an old response from patching a new client incarnation at the
same address without weakening the one-live-proxy-per-address invariant.

There is no server-side `dispose()` hook. A browser cannot reliably notify the
server when a node or tab disappears, and no server resource may depend on
such notification for correctness. Durable cleanup uses an explicit callable
and ordinary transaction. Client disposal also does not revoke an otherwise
valid signed token; replay and server-side invalidation remain the separate
token-freshness concern in `state-model.md`.

### 8. Callable results may introduce configured Glue objects

An authorized callable may directly return one already-configured `BaseGlue`
object as a transient child; it is not limited to returning `Glue.Component`.
Its Glue-object return annotation declares that result shape. The response
pipeline binds the object to the current request, gives it an opaque transient
key beneath the caller's address, caps its capability by the caller's effective
capability and current authorization, issues its independent policy, and
encodes the callable result as a reference that the client resolves to the
registered reactive proxy.

The public `Glue.model`, `Glue.form`, `Glue.queryset`, and `Glue.formset`
shortcuts remain the preferred way to construct and configure such results;
custom `BaseGlue` types are constructed directly. In a callable-result context
the response pipeline supplies lifecycle ownership and the final address;
application code does not flatten or splice transport entries as
`TimeEntryDayGlue._build_time_entry_payload` does today.
Direct adapter construction remains an advanced/internal path rather than the
documented default.

The family shortcuts therefore support two contexts: their established
request-and-name form registers a page-owned object from a view, while their
non-registering construction form omits those values and returns a configured,
unbound object for a child property or callable return. The generic
`Glue.object(request, glue)` helper remains root registration only. Binding an
unbound object as a result supplies the request, generated transient address,
and owner.

```python
class TimeEntryDay(Glue.Component):
    @Glue.attr(required_access=Glue.Access.ADD)
    def new_entry(self, request: HttpRequest) -> ModelGlue:
        entry = TimeEntry(period=self.date, user=request.user)

        return Glue.model(
            target=entry,
            access=Glue.Access.ADD,
            fields=['id', 'period', 'project', 'allocated_hours'],
            form=TimeEntryForm,
        )
```

Creation uses the dedicated `ADD` level from ADR 009. The unsaved model may be
edited and saved as a creation draft, but an ADD-only result becomes `VIEW`
after its signed target identity advances to the persisted primary key. A
callable that needs the resulting row to remain editable must itself require and
return `CHANGE`.

The transient form or model result has no HTML requirement. Client code may
pass its proxy into an existing Alpine/modal scope and explicitly dispose it
when that scope closes; owner disposal and `effects.dispose` remain fallback
terminal paths. A transient result's lifecycle ownership is recorded by the
client registry rather than in the owner's signed `children` map — see
[`state-model.md`](state-model.md) §10 — so disposing it when a modal closes
leaves nothing dangling, and repeated calls do not accumulate in the owner's
token. A returned component additionally produces the standard HTML
envelope and receives automatic disposal when its root is removed. Components
are therefore the convenient rendered case, not a transport requirement.

Glue never turns a raw Django model, form, formset, or queryset into a live
Glue object merely by inspecting its runtime type. Type recognition cannot
infer safe fields, relations, forms, filters, ordering, calls, or access. If a
raw Django object reaches a callable-result or attribute serialization boundary
where no ordinary serializer applies, Glue rejects it loudly and directs the
developer to a configured `Glue.*` shortcut. Developers who intend plain data
must explicitly project it to serializable values.

Glue does not recursively inspect an ordinary dictionary, list, tuple,
dataclass, or other result container for hidden Glue objects. Such a result is
rejected if it contains `BaseGlue` anywhere below its root. A callable may
return ordinary serializable data, one directly declared Glue object, or a
configured addressed collection such as `QuerySetGlue`. A future explicit
`Glue.dict(...)` family may provide mixed named values and children without
weakening this boundary; it is tracked in `roadmap.md`.

The same rule applies to child declarations: a configured Glue object is
introduced only through the shared addressed-object paths above; returning a
raw ORM/form object does not silently expand the public interface. This
preserves automatic transport ergonomics without making automatic exposure a
security policy.

## Evidence: Morph Spike

`django_glue/tests/e2e/test_lab_morph.py` against
`test_project/lab/views/morph_views.py` (`/lab/morph/`). A region of four
cards, each with a stable `id` and `key`, local Alpine state, a text input,
and one card with a subtree written by imperative JavaScript. Re-rendered
server HTML is applied under three strategies. The verified run is 13 passed,
10 failed; every failure is a replace or idiomorph case except Alpine.morph's
full reorder.

| | replace (previous) | idiomorph | Alpine.morph |
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
  `x-for` (§6).
- **Stable ids drive exact relocation.** idiomorph's perfect reorder came from
  `id` matching, which canonical addresses provide.

## Consequences

- **Supersedes `docs/roadmap/proxy_instance_management.md`.** Per-access
  proxy construction existed so proxies were built after Alpine's `initTree`.
  Glue now makes objects reactive itself, when it hands them out or updates
  them rather than when it constructs them, which resolves the start-up
  order (see §2).
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
- **The HTML envelopes are unified.** `GlueTemplateResponse` and negotiated
  `Glue.view` responses use `render_html_payload()` to produce HTML and the
  shared flat `objects` collection. Attribute transports carry the HTML result
  in their addressed response entry; view transports return the HTML envelope
  directly. `client_js/src/htmlRenderer.js` handles the public render methods.
  `TemplateGlue` and its template proxy are removed.
- **`Glue.view` uses the target URL's middleware chain.** It requests the actual
  same-origin target with a Glue-specific `Accept` media type. A response
  middleware packages the rendered HTML and introduced objects, but never changes
  authorization or dispatch. The central redispatch endpoint and synthetic
  request wrapper are removed; views require no Glue-specific decorator or
  registration. The precise transport contract is in `state-model.md` §6.
- **The state transport is governed by `state-model.md`.**
  `takes_client_state` and `updates_client_state` are removed. Requests derive
  editable updates from canonical versus ephemeral state; responses carry an
  addressed successor policy token and `computed_data`, which are assembled and
  reconciled without replacing newer local edits.
- **Stale documentation.** `AGENTS.md` still documents the removed
  `proxies/` package, `@action`, and session-based registration, and
  `docs/architecture.md` is partially stale on signing and expiry.

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
- **Implicit parameter-source detection.** Looking for the same expression in
  Django and Alpine scopes makes typos change trust domains and makes meaning
  depend on incidental context. The template-tag arguments are Django filter
  expressions; Alpine-bound construction remains a separate future design.
- **A component-only private event bus.** It duplicates Alpine's expression,
  modifier, bubbling, and listener-lifecycle machinery and makes ordinary
  `addEventListener()` unable to observe component outcomes. Proxy `$on()`
  remains necessary for non-rendered Glue families, while rendered components
  bridge the same declared event to a standard DOM `CustomEvent`.
- **Ancestor tokens embedded in child policies.** This duplicates state at
  every nesting level, makes token size grow with tree depth, and couples a
  child's authority to unrelated ancestors. Independent per-address policies,
  explicit sequential reactions, and transport-only batching support the same
  interactions without the copies.
- **Public `hydrate()`, `dehydrate()`, or `boot()` hooks.** They allow
  application code to interpose on signed reconstruction, duplicate the
  serializer and injection systems, and encourage per-request side effects.
  Glue keeps the reconstruction pipeline fixed and framework-owned.
- **A server-side `dispose()` hook.** Browser and network teardown is not
  reliable enough to guarantee it runs. Address cleanup is client-side;
  durable application cleanup must be an explicit authorized operation.
- **Implicit adaptation of raw Django objects by runtime type.** A model,
  queryset, form, or formset does not carry an exposure policy. Glue transports
  directly declared, configured `BaseGlue` results but requires a `Glue.*`
  family shortcut or explicit adapter configuration before it creates a live
  client object.
- **Derived data as parameters.** Signs page data into every token and makes it
  stale by construction. Parameters carry inputs; recomputable results remain
  derived output.
- **Keys declared on the component (`key=True`).** Uniqueness is relative to
  the parent, so the same component needs different keys under different
  parents. Blazor and React both key at the render site.
- **A class-level default key with render-site override.** Avoids repeating
  the key, but keeps a list concern on the item and hides the choice from
  the render site where uniqueness is actually decided.
- **A separate `Glue.prop` / `Glue.data_prop` declaration.** Duplicates the
  server-state role of bare `Glue.attr(x)` and splits one established
  vocabulary in two; `parameter=True` separately makes the external input
  contract explicit.
- **Other names for `parameter`.** `suppliable` read poorly; `input` shadows a
  builtin and trips ruff `A002` in glue's own signature; `init` inverts
  dataclasses' opt-out default and collides with Alpine's `init()`;
  `settable` is confusable with client-writable state; `optional` says a
  value is not required but not that it is accepted from outside.
- **Delaying glue's start-up until Alpine loads.** Breaks inline scripts that
  use `Glue` during parsing, including the `Glue.onMessage` setup in spire's
  and the test project's base templates, and requires template changes in
  every project.
- **Keeping Alpine external.** Initially preferred because projects already
  loaded it. Superseded by bundling: one runtime and pinned core/morph versions
  simplify installation. Projects migrate by removing the external core and
  morph scripts; deferred optional plugins still register before Glue starts
  Alpine.
