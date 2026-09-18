# Glue State Management: Audit and Redesign Brief

Date: 2026-09-10
Status: Catalogue complete; redesign sketched, not decided

## Why this exists

Glue has roughly **twenty mechanisms** carrying one concept, and **46 divergent
implementations** of "what is state / identity / metadata":

| Method                       | Implementations |
| ---------------------------- | --------------- |
| `get_identity`             | 8               |
| `_reconstruct_from_policy` | 8               |
| `get_state`                | 7               |
| `get_metadata`             | 7               |
| attribute`state` property  | 7               |
| `_load_client_state`       | 4               |
| JS`_applyResponseData`     | 5               |

Every count below is measured across three real codebases — the library
(`django_glue`), its own tests, `stratusadv-portal`, and `django-spire` — because
library-internal usage and real developer usage diverge sharply, and counting only
one of them produces the wrong answer. (An earlier pass at this reversed its own
conclusion once portal usage was included.)

---

## 1. The catalogue

Verdicts: **KEEP** · **COLLAPSE** (fold into a unified concept) · **DELETE** ·
**VERIFY** (evidence suggests dead, but absence of a grep hit is not proof).

### Signed token layer

| Mechanism                                                          | Does                                             | Evidence                                                       | Verdict                                                                                                                                                                     |
| ------------------------------------------------------------------ | ------------------------------------------------ | -------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `policy.identity`                                                | Values needed to rebuild the object, HMAC-signed | 8`get_identity` impls; only 2 public `identity=True` sites | **KEEP, split**                                                                                                                                                       |
| Attribute allowlist (currently recursive nested policies)          | What may be called                               | Core security; no competitor has it                            | **KEEP THE POSITIVE CAPABILITY, REPLACE THE SHAPE** — each addressed object owns a flat complete-path callable capability; attached objects own independent policies |
| `access` / `session_id` / `request_user_id` / `created_at` | Authorization + binding + expiry                 | Core                                                           | **KEEP**                                                                                                                                                              |

`identity` currently holds three unrelated things — identifying input (`target_pk`),
configuration (`batch_size`), and mutable bookkeeping (`loaded_row_count`,
`last_query_params`). The ADR already names this ambiguity. Splitting it is the
single highest-value change in the token layer.

### Manifest layer

| Mechanism                       | Does                              | Evidence                                        | Verdict                           |
| ------------------------------- | --------------------------------- | ----------------------------------------------- | --------------------------------- |
| `state`                       | Mutable values                    | 7 impls                                         | **COLLAPSE**                |
| `metadata`                    | Frontend hints                    | 7 impls; client reads only 5 keys — see §2.3  | **KEEP, split by audience** |
| `loading_strategy` LAZY/EAGER | Ship state now or fetch on access | LAZY 16 lib / 1 portal; EAGER 9 lib / 2 portal  | **KEEP**                    |
| `loading_strategy` INHERIT    | —                                | **1 occurrence: its own enum definition** | **DELETE**                  |

### Per-call filters

| Mechanism                         | Does                          | Evidence                                             | Verdict                     |
| --------------------------------- | ----------------------------- | ---------------------------------------------------- | --------------------------- |
| `takes_client_state` (bool)     | Whether client state flows up | lib 22, portal 22                                    | **KEEP, rename**      |
| `takes_client_state` (key list) | Ship only named keys up       | **2 uses**, both `dashboard.py`              | **COLLAPSE**          |
| `updates_client_state`          | Whether state flows back down | lib 18 —**8 of them `=False`** — portal 13 | **KEEP, fix default** |

When the library's own code opts out of a default eight times, the default is wrong.
A production comment in `day.py` says so directly: *"they sound like a matched toggle
for one round trip but actually control opposite, independent directions... Revisit
naming/defaults in django-glue itself."* That comment sits above an
`updates_client_state=False` that is load-bearing because the default **clobbered the
client's `entries` collection**.

### Attribute-level state

| Mechanism                                                                                                                                                                                                           | Evidence                                                   | Verdict                                   |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------- | ----------------------------------------- |
| `StateAttribute` / `ReadOnlyAttribute` / `CompositeStateAttribute` / `GlueObjectAttribute` / `ModelFieldAttribute` / `FormFieldAttribute` / `ForeignKeyFieldAttribute` / `RelatedSetFieldAttribute` | 7 distinct`state` implementations                        | **COLLAPSE**                        |
| `CompositeStateAttribute.state`                                                                                                                                                                                   | Returns`{}` with a TODO — never exposes anything        | **FIX or DELETE**                   |
| `ReadOnlyAttribute`                                                                                                                                                                                               | Named read-only;**still hydrated from client state** | **FIX** (this is the security hole) |

### Type-specific channels

| Mechanism                                      | Evidence                                | Verdict                                                                                                                                                                                                                                                                                                                                                         |
| ---------------------------------------------- | --------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `computed_attributes`                        | lib 29 (25 in tests), portal 2, spire 5 | **COLLAPSE** — duplicates `@Glue.property`                                                                                                                                                                                                                                                                                                             |
| queryset`annotations`                        | →`ReadOnlyAttribute`                 | **COLLAPSE** into derived                                                                                                                                                                                                                                                                                                                                 |
| `$fields`                                    | portal 6, spire 64                      | **KEEP** — the form-editing contract, deliberately distinct from object access per `related_object.md`                                                                                                                                                                                                                                                 |
| `_loaded_state` (m2m after save)             | internal                                | **KEEP**                                                                                                                                                                                                                                                                                                                                                  |
| `_last_query_params` / `_loaded_row_count` | signed*mutable* state in identity     | **MOVE** out of identity                                                                                                                                                                                                                                                                                                                                  |
| `batch_size`                                 | used everywhere                         | **KEEP**                                                                                                                                                                                                                                                                                                                                                  |
| `default_factory`                            | lib 10, portal 9, spire 6               | **KEEP**                                                                                                                                                                                                                                                                                                                                                  |
| `glue_factory`                               | portal 1 (`day.py` entries)           | **REPLACE** — keep the addressed-collection capability, but ordinary `Glue.attr` cannot infer or contain `BaseGlue` items; queryset/formset/custom collection adapters declare keyed children explicitly                                                                                                                                             |
| `related_field_config`                       | lib 42, portal 1, spire 0               | **KEEP THE CAPABILITY, REPLACE THE SHAPE.** Explicit relationship projection is required, but it folds into nested `fields`/`exclude` paths; choice sources become separate. The old shape defaults *open*: `fields = self.related_fields or '__all__'` (`foreign_key.py:100`). With no config, a related object exposes **every field**. |
| `value_adapters`                             | lib 4, external 0, one implementation   | **COLLAPSE** into the declaration                                                                                                                                                                                                                                                                                                                         |
| `initial_context_data`                       | lib 8, portal 0, spire 0                | **DELETE** with TemplateGlue                                                                                                                                                                                                                                                                                                                              |

### Entrypoints

| Entrypoint                                | portal      | spire       | Verdict                                                                               |
| ----------------------------------------- | ----------- | ----------- | ------------------------------------------------------------------------------------- |
| `Glue.model(`                           | 24          | 7           | **KEEP**                                                                        |
| `Glue.queryset(`                        | 36          | 15          | **KEEP**                                                                        |
| `Glue.form(`                            | 35          | 24          | **KEEP**                                                                        |
| `Glue.function(`                        | 4           | 1           | **KEEP — migrate, do not delete.** See below                                   |
| `Glue.formset(`                         | 1           | 0           | **KEEP**, thin                                                                  |
| `Glue.template(`                        | **0** | **0** | **DELETE** — client-side `Glue.template.` is also 0                          |
| `Glue.sequence(`                        | **0** | **0** | **DELETE entrypoint**, keep the class (built implicitly by `SequenceAdapter`) |
| `Glue.view(`                            | ~4          | ~12         | **KEEP — promote.** 16 sites; the de facto component mechanism                 |
| `Glue.http.postJson(` / `Glue.fetch(` | 5           | 8           | **KEEP — but see §2.5.** 13 sites bypassing the proxy system entirely         |

**`Glue.function` is live in spire's chart contrib**, via dynamic access my first
census could not see:

```js
// django_spire/core/templates/django_spire/chart/chart.html:44
const proxy = window.Glue?.function?.[this._glue_name];
```

Five chart classes in `django_spire/metric/visual/charts.py` route through
`Chart.glue()` → `Glue.function(...)`. Deleting it breaks charting in every portal
using spire metric visuals. The portal's own 4 registrations, by contrast, have zero
consumers and are dead code — remove those, keep the mechanism.

**`Glue.view` is the most-used non-object entrypoint.** Every site renders a server
template into a region — `renderInnerHtml`, `renderOuterHtml`,
`renderInsertAdjacentHtmlAfterBegin` — frequently stored in `x-data` and re-invoked
to refresh (celery toasts, AI chat messages, crow items). That is the job Livewire
does with islands and Unicorn with `unicorn:partial`. It is already the component
mechanism people reach for, which raises the priority of the middleware-bypass issue
recorded in [`comparative-analysis.md`](comparative-analysis.md) §4.6.

`TemplateGlue` was superseded in practice by `Glue.html_attr`, which has 5 real portal
uses rendering fragments off form and queryset methods. Note that 3 of those 5 pass
`takes_client_state=False, updates_client_state=False` — again fighting the defaults.

### Client layer

| Mechanism                                                                | Evidence                                                                                       | Verdict                                                                          |
| ------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| `_state` flat dict + `_mergeState`                                   | Deletes keys the server didn't send; server always wins                                        | **REPLACE** — see §3                                                     |
| 5 ×`_applyResponseData` overrides                                     | base, fieldBacked, queryset, formset, sequence                                                 | **COLLAPSE**                                                               |
| Listener system (`addListener`/`removeListener`, before/after/error) | **0 consumers anywhere.** Appears only in `AGENTS.md` and `docs/guides/form_glue.md` | **DEPRECATE** — published API on a PyPI package, so deprecate then remove |
| `Glue.onMessage`                                                       | 1 use (spire base template)                                                                    | **KEEP**                                                                   |
| queryset query cache                                                     | the real fix for the infinite-refetch bug                                                      | **KEEP**                                                                   |
| `_metadata`, `_policy`, `_fields`                                  | core                                                                                           | **KEEP**                                                                   |

A fully documented feature — `docs/guides/advanced/event_listeners.md` — has zero
production consumers.

---

## 2. What the catalogue reveals

### 2.1 Dead or near-dead

`LoadingStrategy.INHERIT`, `Glue.template()` + `initial_context_data`,
`Glue.sequence()` as an entrypoint, the three-event listener system, and
`CompositeStateAttribute.state` (returns `{}`). `Glue.function` and the public
shape of `related_field_config` required the later human rulings recorded in
the living state-model design.

### 2.2 Mechanisms fighting their own defaults

`updates_client_state` is explicitly disabled 8 times inside the library and 3 of 5
times in portal `html_attr` uses. That is not configuration; that is a wrong default
being worked around, once per call site, with a comment explaining the trap.

### 2.3 Metadata has two audiences and one channel

The client's *proxy machinery* reads only five things: `attributes[name].namespace`
(to choose an initializer), nested `.metadata`, `.params` (functions),
`.takes_client_state`, and `.name` (aliases). Everything else — field types, labels,
widgets, help text, choices — exists for **template and UI** consumption.

Those two audiences have different lifetimes: construction metadata is needed once
at proxy build; UI metadata is needed whenever something renders. Shipping them in
one blob on every response is why `updates_client_state` had to be invented.

### 2.4 The proxy system only covers CRUD, and developers route around it

Thirteen sites call `Glue.fetch` / `Glue.http.postJson` against hand-written `json:`
views instead of using a proxy. Every one is a case the proxy system has no concept
for:

| What they needed                                 | Sites                                          |
| ------------------------------------------------ | ---------------------------------------------- |
| Reorder a collection                             | `knowledge/entry` reorder                    |
| Poll for updates on an interval                  | `knowledge/entry/file` (`setInterval`, 5s) |
| Rename / delete an object not registered as glue | AI chat rename, delete                         |
| Domain RPC that isn't CRUD on a model            | `submit_answer`, `next_question`           |

The damning one: **`Glue.function` exists precisely for domain RPC, and the portal
registers four functions while consuming none of them** — reaching for raw `fetch`
instead. The abstraction lost to the escape hatch.

Two of these — collection reorder and interval polling — are first-class features in
both Livewire (`wire:poll`, `wire:sort`) and Unicorn (`unicorn:poll`). They are not
exotic requests; they are the ordinary things a component system is expected to do.

Any redesign that only tidies the CRUD path leaves all thirteen sites where they are.

### 2.5 The security hole is a naming failure

`ReadOnlyAttribute` is a `StateAttribute` subclass, and `_load_client_state`
hydrates every `StateAttribute`. So the class whose docstring says "read-only
regardless of the GlueObject's access level" is client-writable. The rule and the
implementation disagree, and the type system permits it.

---

## 3. What survives, and the shape it collapses into

After the cull, the concepts that genuinely earn their place:

1. **Capability** — signed: who, what may be called, at what access, until when.
2. **Reconstruction input** — the minimum needed to rebuild the object server-side.
3. **Derived values** — everything the server can recompute from #2 plus the database.
4. **Bound values** — the two-way set the client may write and the server validates.
5. **Construction metadata** — needed once, to build the proxy.
6. **Presentation metadata** — needed by templates, changes rarely.

### The model: three questions

> **These are the maintainer's model, not the public API.** Developers select a
> value role through `editable=True`, its omission, or `@Glue.property`, and may
> independently expose a declared value to construction with `parameter=True`.
> Glue derives direction, protection and timing from the role. Naming these
> questions in the public interface was drafted and rejected. See
> [`../state-model.md`](../state-model.md) §1–§3.

A **question** here means something asked of every single value, where the answers
are a short fixed list. Pick the right questions and a handful of them describe the
whole system — and the answers tell the framework what to do, with nothing left to
configure per case.

**Question 1 — which way does it travel?**
down only · up and down · never leaves the client · rides in the signed token

**Question 2 — how often does it travel?**
once · whenever it changes · only when asked for

**Question 3 — who may see or change it?**
the access level and the allowlist

Questions 1 and 2 must stay separate, because they are genuinely independent. A form
field's `label` and a component's `total_hours` give the *same* answer to Q1 — both
only ever travel down — but different answers to Q2: the label never changes,
`total_hours` changes constantly. Neither answer can be derived from the other.

Worked against `day.py` / `dashboard.py`:

| Value                     | Which way                          | How often             | Who    |
| ------------------------- | ---------------------------------- | --------------------- | ------ |
| `date`                  | signed token                       | fixed at construction | VIEW   |
| `total_hours`           | down only                          | when it changes       | VIEW   |
| `entries[].description` | up and down                        | when it changes       | CHANGE |
| `start_date`            | signed token,**but mutable** | when it changes       | VIEW   |
| a modal's`open` flag    | never leaves the client            | —                    | —     |

Once a value's three answers are known, everything else is mechanical: whether it
goes in the upward payload, whether it is signed, whether it is believed on arrival,
whether it is re-sent in the response, and when it is fetched.

**The current design already asks these questions — about twenty times, in five
vocabularies:**

| Today                    | Is really asking                                                                                  |
| ------------------------ | ------------------------------------------------------------------------------------------------- |
| `takes_client_state`   | half of Q1 (the upward direction)                                                                 |
| `updates_client_state` | the other half of Q1,**with Q2 mixed in** — hence the confusion and the `day.py` comment |
| `loading_strategy`     | Q2                                                                                                |
| `identity=True`        | Q1 (signed round-trip)                                                                            |
| `ReadOnlyAttribute`    | *intends* Q1 (down only), but does not enforce it — hence the security hole                    |

### Does it absorb everything? No — and that is the useful result

**Dissolves outright:** `computed_attributes` and queryset `annotations` both become
"down only, when it changes." `updates_client_state` disappears entirely — its eight
`=False` uses all mean "don't re-send what didn't change," which a response diff does
by construction. The wrong default stops existing rather than getting renamed.

**Resists — seven things escape three questions:**

| Resists                             | Evidence                                                                                                                                                                                                                                                                                        |
| ----------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Serialization**             | Seven attribute`state` implementations exist to coerce types. The questions are silent on *how* a value is encoded. Livewire needs synthesizers for this; Unicorn needs `typer.py`.                                                                                                       |
| **Grain**                     | `{'value': self.get(), 'errors': self.owner._field_errors...}` — one attribute carrying a **bound** value and **derived** errors in one envelope. FK and related-set state returns *"nested object state when eager, None when lazy"* — Q1 and Q2 tangled in a single method. |
| **Signed + mutable**          | `_last_query_params`, `_loaded_row_count`, and `start_date` all round-trip, are signed or need to be, and change every request. "Rides in the signed token" implicitly assumed *stable*.                                                                                                |
| **Capability is not a value** | The allowlist,`access`, normalized field projection, and configured choice sources are exposure policy. They ride the same signed transport but are not values, so Q1 and Q2 do not apply.                                                                                                    |
| **Effects**                   | `messages` and `redirect` are events consumed once, not state. Livewire keeps these in `effects`, deliberately outside the snapshot.                                                                                                                                                      |
| **Fragments**                 | `render_html_payload` returns `{html, manifest_list}` — state arriving *inside* a rendering, carrying new containers. Not modelled at all.                                                                                                                                               |
| **Grain, again**              | The unit is the**leaf value**, not the attribute. `$fields` is the proof.                                                                                                                                                                                                               |

**The proof that "signed + mutable" is real and already hurting:**

```python
@Glue.attr(takes_client_state=['start_date'])
def previous_week(self) -> dict:
    target_date = datetime.date.fromisoformat(self.start_date) - timedelta(days=7)
```

`start_date` is server-owned and not in identity, so on reconstruction it re-derives
to *this* week — losing wherever the user navigated to. The key-list form of
`takes_client_state` is not an optimisation; it is a workaround for a missing
category, shipping navigation state upward **unsigned** and trusting it.

### The corrected model

- **Q1 — which way it travels**, and therefore whether it needs signing. Governs values.
- **Q2 — how often it travels.** Absorbs `loading_strategy`, `updates_client_state`,
  and the metadata split in §2.3.
- **Q3 — who may see or change it.** Entirely separate from value flow. This one
  already works and is glue's competitive advantage; do not disturb it.
- **Not state, modelled separately:** effects (messages, redirects) and fragments
  (HTML carrying manifests).
- **Refinement:** the unit is the leaf value, not the attribute.
- **Open sub-problem:** serialization/coercion needs an answer these questions do not
  supply.

Three questions and two exceptions, versus twenty-two mechanisms. That the model
survived *with amendments* is a better outcome than surviving clean — every
resistance above corresponds to something currently broken or worked around.

### What components add

From the ADR, still unbuilt: the parameter contract, derivation hooks, addresses and
keys, mount/hydration lifecycle, transient children, cascading parameters, parent
reaction, and targeted invalidation. **Seven of the ADR's ten open questions are
downstream of the state model**, so most should stop being questions once this lands.

Subsequent design work settled independent per-address policies and parent
reaction through selective batching. Explicit, non-reactive parameters are the
initial contract; reactive bindings and cascading parameters are now roadmap
extensions rather than unresolved requirements for the first implementation.
It also settled `mount()` as the only public server lifecycle hook, kept
hydration framework-owned, and made disposal a generation-guarded client
address lifecycle with no server hook. Authorized callables may introduce any
configured Glue object as a transient child; raw Django objects are never
auto-exposed without the policy supplied by a public `Glue.*` shortcut or an
explicit adapter. Later design also settled explicit `$refresh()` on every
addressed proxy and declared server-to-client semantic events scoped to their
source address. These events replace neither state nor the removed
`before` / `after` / `error` transport hooks; composition listeners may react
by refreshing another independently authorized proxy.

---

## 4. Borrowing, deliberately

### Take from Livewire

- **`canonical` / `ephemeral` / `reactive`** — three named copies instead of one
  `_state` that the server overwrites. This is what makes local edits survive a
  response.
- **Path-keyed `updates`** — send a diff of changed paths, not the whole blob.
- **`diffAndPatchRecursive` on the way back** — patch only what actually changed, so
  the field a user is typing in is never clobbered.
- **One container, and features as modifiers *inside* it** — `#[Locked]`,
  `#[Computed]`, `#[Reactive]` add no new channels. This is the discipline glue most
  needs: adding a feature must not add a path.
- **Islands** — isolated re-render regions, a direct answer to "targeted invalidation."

### Take from Unicorn

Little. Its `Meta.exclude` / `javascript_exclude` / `safe` model is a weaker version
of what glue already does. Its two CVEs are the argument for **not** drifting toward
deny-list exposure as components make exposure more automatic.

### Do not take

- **Render-first updates** (both) — re-rendering the component per interaction throws
  away glue's main performance advantage.
- **Deny-list exposure** (both).
- **Snapshot-carries-all-data** (Livewire) — glue rebuilds from identity and re-reads
  authoritative data, which is better; keep it.

### Preserve — these are the competitive advantages

Opt-in exposure · per-object capability signing with an access cascade · user/session
binding and expiry · state-first updates · ORM-native queryset objects · no component
ceremony required for simple bindings.

---

## 5. Rulings

### Settled

1. **`Glue.function` — keep the mechanism, delete the portal's dead registrations.**
   Live in spire charts via dynamic access. Replacing it with `Glue.attr` on an
   object is a viable migration, but it is a migration, not a deletion.
2. **Related-field capability — keep, replace the public shape, and close the
   default.** Explicit nested projection remains necessary, but
   `related_field_config` is folded into normal field paths with optional
   `Glue.fields()` sugar; its choice query moves to a separate mapping. The old
   shape defaults to `'__all__'` on related objects. This is a security fix, not
   merely cleanup, because field projection governs exposure.
3. **Listener system — deprecate, then remove.** Zero consumers, but published API.
4. **`TemplateGlue` — remove.** No external users. `Glue.html_attr` covers the case
   with 5 real portal uses. `test_project`'s arena page needs reworking first.
5. **Does the model in §3 absorb every mechanism?** — **Resolved: no, and the misses
   are the point.** Three questions cover most of it; seven things escape, each
   corresponding to something already broken (see §3). The model stands with
   amendments: two extra categories that are not state, one grain refinement, and
   serialization left as an open sub-problem.
6. **Does the redesign absorb §2.4, or only the CRUD path?** — **Resolved: design for
   them, do not build them yet.** The model must leave room for collection mutation
   (a list having an *order*, not just membership) and for time-based refresh, even
   though neither ships in the first release. Every design decision gets tested
   against "could a reorder or an interval refresh live here later?" and anything
   that forecloses either is rejected.

   The cost today is a constraint on the design, not extra code. The failure this
   avoids is shipping a clean CRUD-only model and discovering in six months that
   collections and refresh cannot fit without a second overhaul — while the thirteen
   escape-hatch sites keep multiplying, each running on hand-maintained per-view
   permissions rather than glue's access cascade.
7. **How are values serialized and coerced?** — **Resolved: annotation for *what*,
   registry for *how*.** The declared type hint
   (`date: datetime.date = Glue.attr(...)`) names the target type; a registry of type
   handlers — Livewire's synthesizer model — performs the conversion in both
   directions. Handlers are registerable by consuming projects, over a built-in set
   covering Django's common types, so a project with its own value types never has to
   fall back to hand-coercion.

   This is deliberately narrower than annotation-driven *declaration*, which was
   rejected as too implicit. `Glue.attr` still declares state explicitly; the
   annotation is consulted only to answer "coerce back to what?" A missing annotation
   falls back to the registry or leaves the value untouched — nothing silently becomes
   state, and nothing silently breaks.

   Replaces four scattered mechanisms: `GlueResponseJSONEncoder`, the seven attribute
   `state` implementations, the client's `parseFieldValue` type special-casing, and
   hand-written coercion of the kind in `day.py`
   (`datetime.date.fromisoformat(policy.identity['date'])`).

---

All seven rulings are settled. The next artifact is the ADR — the API surface, the
wire format, and the migration path — built on the three questions in §3 and the
constraints recorded above. Deliberately not attempted in this document: designing on
top of an unvalidated cull is how the current sprawl happened.
