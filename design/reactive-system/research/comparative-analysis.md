# Django Glue vs django-unicorn vs Livewire

Date: 2026-09-10
Author: analysis pass over all three codebases (not a summary of marketing pages)

## Scope and method

| Project | Version reviewed | Source |
|---|---|---|
| django-glue | 1.0.1 (`chasem/component-system`, uncommitted working tree) | this repo |
| django-unicorn | 0.67.0 (`63043f4`, 2026-03-07) | github.com/adamghill/django-unicorn |
| Livewire | v4.4.4 / v3.8.8 maintained in parallel (`e8b8c13`, 2026-09-10) | github.com/livewire/livewire |

Both comparison projects were cloned and read at source level — request pipelines,
checksum/signing code, property hydration, and the JS clients — not just their docs.
Claims about Glue's behaviour marked **verified** were confirmed by executing code
against this repo's `test_project`; the probe file and how to re-run it are in the
appendix.

Today's date is used to judge maintenance recency.

> **The tree moved during this review.** A minimal `Component` base class
> (`django_glue/glue/component.py`, exposed as `Glue.Component`) landed while this
> analysis was being written: a `BaseGlue` subclass that owns a template path and
> exposes a `render()` attribute. It is *not* registered in `glue_class_registry`, so
> a client-initiated call cannot reconstruct one yet — components render server-side
> only. The parameter contract, identity attributes, addresses, keys, stamping, and
> lifecycle remain unbuilt. Statements below reflect that state.

---

## 1. Executive summary

**The three projects are not the same kind of thing, and that is the most important
finding.** Unicorn and Livewire are *component frameworks*: the unit of work is a
component class plus a template, and every interaction re-renders that template on
the server and patches the DOM. Glue is an *object-binding layer*: the unit of work
is a Python object (model, queryset, form, function, or a custom `BaseGlue`) exposed
to JavaScript as a proxy, with values — not HTML — on the wire.

That difference cuts in Glue's favour more often than the star counts suggest:

- **Glue's authorization model is the strongest of the three.** It signs a
  *capability* (which object, which attributes, which access level, bound to which
  user and session, expiring when) rather than signing *data*. Unicorn and Livewire
  both expose every public property and method by default and police that surface
  with deny-lists; Unicorn has needed two CVE fixes to keep that deny-list honest.
  Glue's opt-in `@Glue.attr` exposure is materially safer by construction.
- **Glue's state-first update model is a real performance and correctness
  advantage.** Unicorn and Livewire re-render the whole component per interaction.
  Glue sends a JSON state diff and lets Alpine bindings update the DOM.
- **Glue's data integrity is its weak flank.** Livewire HMACs the entire snapshot
  and adds `#[Locked]`, rate limiting, and payload guards. Glue signs the capability
  but accepts client state back with no integrity protection and no lock — and
  **`identity=True` does not protect a value from client tampering** (verified,
  §4.2). That matters enormously for the component system now being designed, where
  identity attributes are meant to be the trust anchor.
- **The maturity gap is not close.** Livewire is an industrial framework component
  with a company behind it (23.5k stars, ~2050 tests, weekly releases). Unicorn is
  a community library with one maintainer, slowing down (last push 2026-05-22).
  Glue is an internal library with a public repo (7 stars, 0 forks, one org).

Glue should not try to out-feature Livewire. It should close five specific security
gaps before the component system ships, and keep the state-first, capability-signed,
ORM-native model that makes it different.

---

## 2. Architecture

### 2.1 The fundamental split

| | django-glue | django-unicorn | Livewire |
|---|---|---|---|
| Unit of work | A Python object exposed as a JS proxy | A component class + template | A component class + Blade view |
| Must you define a component? | No | Yes | Yes |
| What crosses the wire on interaction | JSON state + result | Full component state + full re-rendered HTML | Full snapshot + full re-rendered HTML |
| DOM update | Alpine reactivity; `Alpine.morph` only for HTML replacement | Server re-render → morphdom (or Alpine morph) | Server re-render → custom morph; v4 islands scope it |
| Frontend framework | Alpine (bundled, hard dependency as of this branch) | None required; optional Alpine morpher | Alpine (bundled, hard dependency) |
| Server-side state between requests | None (stateless tokens) | Component pickled into Django cache | None (stateless snapshot) |

Unicorn and Livewire are **render-first**: an interaction produces HTML. Glue is
**state-first**: an interaction produces values, and the DOM follows from Alpine
bindings. [`../component-system.md`](../component-system.md) explicitly rejects regressing to
render-first, and that is the right call — it is Glue's clearest technical
differentiator.

### 2.2 Request lifecycle

**Glue.** A view calls `Glue.model(...)` / `Glue.queryset(...)` / `Glue.object(...)`.
Each registers a `GlueManifest` on the request containing a signed policy token,
metadata, and (if eager) state. `{% django_glue_init %}` serialises the manifest list
into the page; `GlueClient` builds one Alpine-reactive proxy per registered name.
An attribute call POSTs `multipart/form-data` to
`/__dg__/callable_attribute/<object>/<attribute>/` carrying `policy_token`, `state`,
`attribute`, `kwargs`. The server verifies the token, reconstructs the object from
the signed `identity`, hydrates client state, checks access, and calls the attribute.
The response carries `result`, a renewed `policy_token`, and (unless
`updates_client_state=False`) fresh `state` and `metadata`.

**Unicorn.** `{% unicorn 'hello-world' %}` finds `HelloWorldView` by convention,
renders its template, and serialises every public attribute into a `unicorn:data`
JSON attribute plus a checksum. The JS client scans for `unicorn:`/`u:` attributes.
An interaction POSTs `{id, data, meta/checksum, epoch, actionQueue}` to
`/message/<component_name>`. The server validates the checksum over `data`, restores
the component from the Django cache (pickle) or recreates it, applies `data`, runs the
action queue — method names are parsed with `ast.parse` + `ast.literal_eval` — then
re-renders the whole template and returns the HTML for morphdom to patch.

**Livewire.** Mount renders HTML carrying `wire:snapshot` (`data` + `memo` +
`checksum`) and `wire:effects`. An interaction POSTs
`{components:[{snapshot, updates, calls}]}`. The server verifies an HMAC-SHA256
checksum over the snapshot, hydrates properties through *synthesizers* (typed
per-PHP-type serialisers: `ArraySynth`, `CarbonSynth`, `EnumSynth`, `ModelSynth`…),
applies updates, calls methods, re-renders, dehydrates to a new snapshot, and returns
snapshot + effects.

### 2.3 Where state lives — the key architectural axis

- **Livewire:** all component state round-trips through the client, integrity-protected
  by an HMAC over the whole snapshot. Nothing server-side between requests.
- **Unicorn:** state round-trips through the client (checksum over `data`) *and* the
  component is pickled into the Django cache to preserve non-serialisable bits.
  Two sources of truth, reconciled per request.
- **Glue:** the *capability* round-trips signed; the *state* round-trips unsigned.
  Objects are rebuilt from a signed `identity` (a model pk, a template path, a
  function path) and then hydrated with unsigned client state.

Glue's design is the most economical, and rebuilding from identity means the server
re-reads authoritative data from the database rather than trusting a client copy —
genuinely better than both. The gap is that once an object *does* carry declared
state, nothing distinguishes "server owns this" from "client may set this."

### 2.4 Composition

| | Glue | Unicorn | Livewire |
|---|---|---|---|
| Nested units | `GlueObjectAttribute` nests a glue object with its own signed policy | Child components with `$parent` access | Nested components; `wire:key`; slots |
| Identity of a child | Hand-written global string today; addresses designed in the ADR | Component id + optional key | Component id + key |
| Props down | Constructor args (component parameter contract designed, not built) | Kwargs on the template tag | Blade attributes; `#[Reactive]` to opt into live updates |
| Events up | Window events / listener callbacks | `$parent` method calls, JS `Unicorn.call` | `dispatch()` events, `#[On]` listeners |
| Scoped re-render | Not yet (ADR "targeted invalidation" open) | `unicorn:partial` by id/key | v4 `@island` — isolated regions inside one component |

Composition is where Glue is furthest behind, and the working branch knows it: the
ADR's "what still hurts" section documents stringly-typed child names, template
inputs that carry the *text* of a JS identifier, and invalidation via window events.
Livewire's islands are worth close study — they solve the ADR's open "targeted
invalidation" question without requiring child components.

---

## 3. Feature comparison

Legend: ● full, ◐ partial / manual, ○ absent.

| Capability | Glue | Unicorn | Livewire |
|---|---|---|---|
| Model instance binding | ● | ◐ (via plain attrs) | ● |
| QuerySet as a client object (filter/order/paginate) | ● keyset + batching | ○ | ○ (server-side `WithPagination`) |
| Form / ModelForm integration | ● | ● | ● (form objects) |
| FormSet | ● | ○ | ○ |
| Call a Python function from JS | ● | ◐ (component methods) | ◐ (component methods) |
| Server-rendered fragment on demand | ● (`Glue.view`, `TemplateGlue`) | ◐ (`unicorn:partial`) | ● (islands, `wire:stream`) |
| Declarative model binding directive | ○ (write Alpine yourself) | ● `unicorn:model` + lazy/defer/debounce | ● `wire:model` + modifiers |
| Declarative action directive | ○ | ● `unicorn:click` etc. | ● `wire:click` etc. |
| Component definition + mounting | ◐ base class only; contract unbuilt | ● | ● |
| Per-field access control | ● VIEW/CHANGE/DELETE + field filtering | ◐ `Meta.exclude` | ◐ `#[Locked]` |
| Validation surface | ● Django forms + `full_clean` | ● | ● |
| Loading states | ◐ `loading` flag on some proxies | ● | ● `wire:loading` |
| Dirty states | ○ | ● | ● `wire:dirty` |
| Polling | ○ | ● | ● `wire:poll` |
| Lazy render on visibility | ◐ lazy/eager loading strategy | ● | ● `#[Lazy]` |
| File uploads | ◐ multipart through state | ○ | ● temp storage, progress, S3 |
| Inter-component events | ○ (window events by hand) | ◐ | ● |
| URL / query-string binding | ○ | ○ | ● `#[Url]` |
| SPA navigation | ○ | ○ | ● `wire:navigate` |
| Streaming responses | ○ | ○ | ● |
| Request batching / pooling | ○ | ◐ queue/serial | ● |
| Testing harness | ○ | ◐ | ● `Livewire::test()` fluent API |
| CSP-safe build | ○ | ○ | ● `csp_safe` |
| Event listener hooks (before/after/error) | ● | ◐ signals | ● interceptors/hooks |
| Redirects from server | ● | ● | ● |
| Messages / toasts | ● | ● | ● |
| CLI scaffolding | ○ | ● `startunicorn` | ● `make:livewire` |

Two honest readings of this table:

1. Glue wins the rows nobody else competes in — queryset-as-a-client-object,
   formsets, direct function calls, per-field access levels. These are ORM-native
   capabilities that fall out of the object-binding model.
2. Glue loses nearly every *ergonomics* row. There are no directives; the developer
   writes Alpine by hand and binds proxies by string name. That is the pain the
   component branch exists to fix.

---

## 4. Security

### 4.1 Threat models compared

| Control | Glue | Unicorn | Livewire |
|---|---|---|---|
| Integrity of client-held state | ○ none (state unsigned) | ● HMAC checksum over `data` | ● HMAC-SHA256 over whole snapshot |
| Integrity of the capability (what may be called) | ● signed attribute allowlist + access level | ○ deny-list of names, unsigned | ○ all public members callable |
| Exposure model | ● opt-in (`@Glue.attr`) | ○ opt-out (`_is_public` deny-list) | ○ opt-out (all public props/methods) |
| Bound to user | ● `request_user_id` checked every call | ○ | ○ (persistent middleware instead) |
| Bound to session | ● `session_id` checked every call | ○ | ○ |
| Capability expiry | ● `created_at` + max age | ○ | ○ |
| Lock a value against client writes | ○ **none — see 4.2** | ◐ `Meta.exclude` | ● `#[Locked]` |
| Re-apply route middleware on updates | ○ **see 4.6** | ◐ LoginRequiredMiddleware + `Meta.login_not_required` | ● persistent middleware |
| Rate limit on integrity failures | ○ | ○ | ● 10 failures / 10 min per IP |
| Payload guards | ○ | ○ | ● size 1MB, nesting 10, 50 calls, 200 components |
| Request-authenticity header check | ○ | ○ | ● `RequireLivewireHeaders` |
| Dangerous-class deny-list (deserialisation defence in depth) | ○ | ○ | ● `SecurityPolicy` |
| CSRF | ● Django CSRF + `X-CSRFToken` | ● `csrf_protect` | ● `web` middleware group |
| Output escaping | ● Django autoescape | ● + opt-in `Meta.safe` | ● Blade escaping |

**The one-line framing: Unicorn and Livewire sign the data; Glue signs the
capability.** Glue's approach is architecturally stronger for authorization — an
attacker cannot add an attribute to the allowlist, raise the access level, or reuse a
token as another user or in another session. But Glue currently has *no* answer for
data integrity, and Livewire has a good one.

### 4.2 Verified: client state overrides signed identity attributes

The most significant finding, because it undermines the trust anchor the component
system is being built on.

[`../component-system.md`](../component-system.md) §4 specifies that identity attributes are
"required parameters: everything needed to rebuild the component," signed into the
policy. In practice a value declared `Glue.attr(identity=True)` is *also* collected as
a `StateAttribute`, and `BaseGlue._load_client_state()` applies any `StateAttribute`
from the client payload with `setattr` before the attribute call runs:

```python
# django_glue/glue/base.py
for name, attribute in self.attributes.items():
    if not isinstance(attribute, StateAttribute):
        continue
    if name not in state:
        continue
    setattr(self, name, value)
```

`ReadOnlyAttribute` — despite the name and the docstring "read-only regardless of the
GlueObject's access level" — subclasses `StateAttribute`, so it is hydrated too.

Verified against `test_project`: a glue object signed with `owner_id=5` returns `999`
from an attribute that reads `self.owner_id` when the client posts
`state={"owner_id": {"value": 999}}`. The signed identity only seeds reconstruction;
it does not survive hydration.

Built-in `ModelGlue` is not affected for the pk — the pk is used to *fetch* the
instance and `_apply_state()` only touches editable included fields. The exposure is
custom `BaseGlue` subclasses today, and every component tomorrow.

This is the concrete failure behind the ADR's own open question "**Signed mutable
state** … they are neither parameters nor state. Where they live is unresolved."
Resolving it in the safe direction is a small change: skip identity attributes and
`ReadOnlyAttribute`s in `_load_client_state`. That gives Glue a `#[Locked]` equivalent
essentially for free, and it should land *before* components depend on identity.

**The new `Component` class raises the stakes.** `Component.render()` is declared with
the default `takes_client_state=True` (its test asserts exactly that), and
`get_context_data()` puts the component instance itself into the template context. So
once components are client-reachable, the sequence is: client state is applied to the
component, then the component renders itself into HTML with that state in scope. Any
declared attribute a component carries — identity or not — is client-settable unless
this is fixed first. Two things currently stand between that and exploitability:
components are not registered in `glue_class_registry`, and they have no declared
state attributes yet. Both are about to change. Fixing hydration now costs a few
lines; fixing it after the parameter contract ships means changing semantics that
component authors already depend on.

### 4.3 Verified: client kwargs outrank injected `HttpRequest`

`CallableAttribute._resolve_call_parameter()` checks client-provided kwargs *first*,
before injecting `HttpRequest` by type hint:

```python
if param_name in call_parameters:      # client wins
    return call_parameters[param_name]
if type_hint is not None and issubclass(type_hint, HttpRequest):
    return context.request
```

Verified: an attribute declared `def request_type(self, request: HttpRequest)` receives
a `str` when the client posts `kwargs={"request": "spoofed"}`.

Realistic impact is usually a 500 (attribute access on a `str`/`dict` fails) rather
than an auth bypass, so this is a footgun rather than a hole — but any attribute that
authorises off `request.user` is written on the assumption that `request` is genuine.
Context injection should win over client input, or colliding kwarg names should be
rejected. There is no use case for letting the client supply `request`.

### 4.4 Verified: queryset filter allowlist is shallow, order_by is unchecked

`QuerySetGlue._filtered_and_ordered()` validates only the first segment of each
filter key:

```python
base_field = key.split('__')[0]
if base_field not in allowed_fields:
    raise GlueQuerySetFilterValidationError(...)
```

`order_by` receives no validation at all. Verified against `test_project`, with a
queryset exposing only `name` and `skills`:

| Request | Result |
|---|---|
| `filter={'rank_points__gte': 5000}` | 422 rejected (correct) |
| `filter={'skills__gorillas__rank_points__gte': 5000}` | **200, filtered on the unexposed field** |
| `order_by=['-rank_points']` (fields=`['name']`) | **200, ordered by the unexposed field** |

This is the classic Django ORM relation-traversal oracle — the family that produces
`user__password__startswith` attacks. With a relation exposed, an attacker can filter
and sort on fields that were deliberately excluded, on the bound model *and on related
models*, extracting values a character at a time. Neither Unicorn nor Livewire is
exposed here because neither ships a client-drivable queryset; this risk is the price
of Glue's best feature and deserves a proper allowlist over the full lookup path plus
an explicit policy for relation traversal (`related_field_config` already knows what
is exposed).

### 4.5 Verified at the Django level: template context override

`TemplateGlue.render_html()` merges client kwargs over the context:

```python
merged_context = {**context_data, **kwargs}
```

Django pushes an explicit context dict *above* context-processor output, so a client
value shadows the processors. Verified on Django 5.2.17: a template rendering
`{{ user.is_staff }} {{ perms.app.delete_x }}` prints `False False` for an anonymous
user, and `True True` when the caller supplies `{'user': {'is_staff': True}, 'perms':
{'app': {'delete_x': True}}}`.

Consequence: template gating such as `{% if perms.app.delete %}` or
`{% if user.is_staff %}` is not trustworthy inside a `Glue.template` render, because
the client chooses the context. The signed `initial_context_data` is overridable by
unsigned client kwargs. Namespacing client kwargs under a single key, or refusing keys
that collide with context-processor names, would close this.

### 4.6 By inspection: `Glue.view` bypasses path-scoped middleware

`GlueViewFragmentResolver._call_resolved_view()` takes a client-supplied URL path,
resolves it, and calls the view function directly:

```python
resolved = resolve(parsed.path)
return resolved.func(self._build_glue_view_http_request(context), **resolved.kwargs)
```

View decorators (`@login_required`, `@permission_required`) still run because they wrap
the function. Middleware does **not** — the middleware chain already ran for
`/__dg__/glue_view/`, not for the target path. Any authorization implemented as
path-scoped middleware (tenant scoping, IP allowlists, custom permission middleware,
`LoginRequiredMiddleware`'s per-view checks against the *target*) is skipped.

This is precisely the problem Livewire solves with persistent middleware, which
re-applies the original route's middleware to every update request and is documented
as a first-class security feature. It is the closest thing to a structural security
difference between the two projects, and it will get more load-bearing as
`Glue.view` becomes the mounting path for components.

Mitigating factors: only URL-resolvable internal paths are reachable, external
redirects are refused, and tracebacks are only exposed when `DEBUG` is on (the
`GlueRequestError` for a failed view embeds `traceback.format_exc()`, but
`GlueResponse.from_error` withholds details for 5xx unless `DEBUG`) — that last part
is handled correctly.

**Design disposition:** `state-model.md` §6 removes internal redispatch. The client
requests the actual same-origin target URL, and response middleware performs only
content negotiation after normal Django dispatch. The target path therefore passes
through the complete middleware chain; requesting the Glue response media type does
not grant authority.

### 4.7 By inspection: signed pickle in the client-held token

`QuerySetGlue` and related-field choice querysets serialise the ORM `Query` with
`pickle` + base64 into `identity`, which is signed into the policy token and shipped
to the browser:

```python
return base64.b64encode(pickle.dumps(queryset.query)).decode('utf-8')
```

The signature makes this not directly exploitable, and the token is verified before
`pickle.loads` runs. Two second-order concerns:

- It upgrades a `SECRET_KEY` disclosure from "session forgery" to "remote code
  execution." Django removed the pickle session serialiser for exactly this reasoning.
- Token size grows with query complexity. The settled design avoids duplicating
  ancestor tokens, but still requires limits for each independently signed
  object and for aggregate selectively batched requests.

Livewire's synthesizers exist specifically to avoid generic deserialisation, and after
a published gadget-chain disclosure Livewire *also* added a `SecurityPolicy` deny-list
of dangerous classes as defence in depth even behind the checksum. Unicorn pickles
only into the server-side cache, never to the client. Glue is the only one of the
three shipping pickled payloads to the browser.

### 4.8 Smaller items

These operational and defence-in-depth items are tracked as non-gating work in
[`../roadmap.md`](../roadmap.md). Query-token size checks before deserialization remain
part of the state-model implementation rather than roadmap hardening.

- **Default policy lifetime is 24h in code, 600s in docs.**
  `django_glue/settings.py` sets `DJANGO_GLUE_PROXY_POLICY_MAX_AGE_SECONDS = 86400`
  while `docs/guides/advanced/configuration.md` documents 600 and
  `docs/architecture.md` says 3600. A capability token valid for a day is a long
  replay window for a stolen token; whatever the intended value, three numbers for one
  security control is a documentation defect worth fixing.
- **No rate limiting on signature failures.** Livewire blocks an IP after 10 checksum
  failures in 10 minutes. Glue will answer unlimited forged-token probes.
- **No payload guards.** No max request size, nesting depth, or call count; Livewire
  has all four. Django's `DATA_UPLOAD_MAX_MEMORY_SIZE` is the only backstop.
- **Session churn.** `GlueContextManager.add_glue()` calls `request.session.create()`
  for anonymous visitors on any page with a glue object, writing a session row per
  anonymous visitor. Unicorn and Livewire do not require a session.
- **Session-key rotation invalidates every token.** Django's `cycle_key()` on login
  means tokens minted before login stop verifying — correct security behaviour, but a
  UX cliff worth documenting (a page open in another tab breaks on login elsewhere).
- **CSP.** Glue bundles standard Alpine (`new Function`) and `{% django_glue_init %}`
  emits an inline `<script>`, so `unsafe-eval` plus `unsafe-inline`/nonces are
  required. Livewire ships a CSP-safe build that swaps Alpine's evaluator. Unicorn has
  no CSP story either, so this is parity-with-Unicorn, behind-Livewire.

### 4.9 Published vulnerability history

| Project | Advisories | Notable |
|---|---|---|
| django-glue | none | no published advisories; also almost no external users |
| django-unicorn | 2 | **CVE-2025-24370 (critical)** class pollution via `set_property_value` → RCE/XSS/DoS/auth bypass, fixed 0.61.0; **CVE-2026-31815 (medium)** `_is_public` bypass letting a client set `template_name` and render arbitrary templates, fixed 0.67.0 |
| Livewire | 3 | **CVE-2025-54068 (critical)** RCE via property-update hydration (v3 < 3.6.4); **CVE-2024-47823 (high)** file-upload extension bypass → RCE; **CVE-2026-81887 (medium)** DOM XSS in client-side state handling |

Read this as evidence, not as a scoreboard. **Both comparison projects have shipped
critical RCEs in exactly the mechanism Glue is now building** — client-driven property
hydration. Unicorn's two CVEs are both failures of the deny-list exposure model, which
is the strongest available argument that Glue's opt-in `@Glue.attr` model is the right
one and must not erode as components make exposure more automatic.

Glue's clean record reflects an absence of attackers, not proof of hardness.

---

## 5. Stability and maturity

| | Glue | Unicorn | Livewire |
|---|---|---|---|
| Stars / forks | 7 / 0 | 2,664 / 131 | 23,574 / 1,746 |
| Open issues | 1 | 51 | 16 |
| First commit | 2022-05 | 2020-07 | 2019-02 |
| Latest release | v1.0.1 (2026-09-04) | 0.67.0 (2026-03-07) | v4.4.4 (2026-09-07), v3.8.8 in parallel |
| Release cadence | sporadic; v1.0.0 days ago | ~monthly, slowing | weekly, two supported majors |
| Last push | today | 2026-05-22 (~4 months) | today |
| Maintainers | one company (Stratus) | one primary maintainer | company-backed (Laravel ecosystem) |
| Python/PHP tests | ~381 + 25 e2e | ~596 | ~2,050 |
| JS tests | ~113 | ~207 | vitest suite + 81 Dusk browser test files |
| CI | ruff, py 3.11–3.13, Django 5.0–6.1 matrix (subset), bun, Playwright | pytest, JS, playwright | full matrix, browser suite |
| Docs | mkdocs site, guides + API ref | Sphinx site, ~30 pages | extensive; includes a written protocol spec, hydration internals, security page, upgrade guides |
| Declared status | PyPI classifier still `Development Status :: 3 - Alpha` despite v1.0.1 | 0.x after 6 years | 4.x stable |

**Glue's engineering practice is better than its adoption suggests.** The CI matrix
(three Python versions, six Django versions, JS unit tests, Playwright e2e) is
comparable in shape to Unicorn's, and the ADR/handoff discipline in this repo is
better than either comparison project's. What is missing is *external* validation:
zero forks means no one outside the org has stress-tested it.

Three stability risks specific to Glue right now:

1. **Actively breaking its own API.** Bundling Alpine is a breaking installation
   change for every consuming project; `renderOuterHtml`'s single-root requirement is
   a deliberate breaking behaviour change. Both landed *after* v1.0.0 shipped. A
   library that reached 1.0 nine days ago and is making breaking changes on its main
   development branch is signalling that 1.0 was premature — the PyPI Alpha classifier
   is arguably the honest one.
2. **The component system is barely started.** A `Component` base class exists as of
   this review (template path + `render()`); the parameter contract, identity
   attributes, addresses, keys, stamping, and lifecycle are all pending, with a dozen
   open questions still unresolved in the ADR. That is a large amount of unbuilt
   surface, and it is the surface the library's next release is being shaped around.
3. **Documentation drift is already measurable.** `AGENTS.md` documents a removed
   `proxies/` package, `@action`, and session-based registration; `docs/architecture.md`
   is stale on signing and expiry; the policy max-age is documented three different
   ways. The ADR itself lists this under Consequences.

By comparison, Unicorn's risk is **maintenance velocity** (one maintainer, four months
quiet, still 0.x), and Livewire's risk is essentially **only the framework lock-in**
(it is not a Django option at all) — its engineering health is excellent.

---

## 6. Where Glue genuinely stands

### Real advantages over both

1. **Opt-in exposure.** `@Glue.attr` allowlisting versus policing every public member
   with a deny-list. Unicorn's CVE history is the empirical case for this.
2. **Signed capabilities with an access cascade.** VIEW/CHANGE/DELETE enforced server
   side on every call, per object, with the attribute allowlist inside the signature.
   Neither competitor has a built-in per-object permission level; Livewire's security
   docs are mostly "remember to call `$this->authorize()` yourself."
3. **User- and session-bound, expiring tokens.** A stolen token is useless in another
   session or under another user.
4. **State-first updates.** JSON diffs instead of a full component re-render per
   interaction.
5. **ORM-native client objects.** Client-drivable querysets with filtering, ordering,
   and keyset pagination; formsets; direct function calls. Nobody else offers this.
6. **No component ceremony required.** You can glue one queryset into an existing
   Alpine page. Unicorn and Livewire require you to define a component for everything.

### Real gaps

1. **No data-integrity/lock concept** (§4.2) — the highest-priority item.
2. **No usable component model yet** — a base class exists; composition, parameters,
   and identity do not.
3. **No declarative directives**; names are bound as strings, which the ADR documents
   as an active source of production bugs ("a library rename shipped a broken modal").
4. **Incomplete ORM input validation** (§4.4).
5. **No hardening layer** — rate limits, payload guards, CSP build.
6. **No testing story** for consumers; Livewire's `Livewire::test()` is a major
   adoption feature.
7. **Ecosystem of one.**

---

## 7. Recommendations

**Before the component system ships** (all are small, all are in Glue's own control):

1. Make `_load_client_state()` skip identity attributes and `ReadOnlyAttribute`s.
   This resolves the ADR's "signed mutable state" open question in the safe direction
   and gives Glue a `#[Locked]` equivalent. (§4.2)
2. Give context injection priority over client kwargs in
   `CallableAttribute._resolve_call_parameter()`, or reject colliding kwarg names. (§4.3)
3. Validate the full lookup path in queryset filters and validate `order_by` at all;
   decide relation-traversal policy explicitly against `related_field_config`. (§4.4)
4. Remove `TemplateGlue`, which has no consuming-project callers and is superseded by
   component and view rendering. This removes its context-shadowing path. (§4.5)
5. Send `Glue.view` requests to the actual target URL and use response-only content
   negotiation, as settled in `state-model.md` §6. This runs the target through its
   normal middleware chain without an allowlist or partial middleware replay. (§4.6)
6. Reconcile the three documented values for the policy max age, and consider whether
   24h is the intended default. (§4.8)

**Worth stealing from Livewire:**

- `#[Locked]` semantics (see item 1).
- Payload guards (size, nesting depth, call count) and checksum-failure rate limiting.
- **Islands** — isolated re-render regions inside one component. This is a direct
  answer to the ADR's open "targeted invalidation" question and avoids forcing every
  independently-updating region to become a child component.
- A written protocol spec. Livewire's `the-livewire-protocol.md` and `hydration.md`
  are why third parties can reason about it; Glue's wire format currently lives only
  in code.
- A consumer testing API.

**Worth stealing from Unicorn:** little, security-wise — its exposure model is the
weaker one. Its `custom-morphers` pluggability is mildly interesting, but this repo's
own morph spike already found that a framework-agnostic morph seam is a trap with
Alpine, so Glue is right to have rejected it.

**Positioning.** Glue's identity is state-first, capability-signed, ORM-native object
binding. The component system should make composition ergonomic without becoming
"django-unicorn with Alpine" — the ADR already commits to this and should be held to
it. The honest pitch against Unicorn is *"opt-in exposure, per-object permissions, and
values on the wire instead of HTML."* There is no honest pitch against Livewire on
maturity; there is one on programming model.

---

## Appendix: reproducing the verified findings

The probe file lives at
`/tmp/claude-1000/-home-chasemossing-stratus-dev/ef3fd5a4-b3ac-43ee-84e3-e5fc873fdcf6/scratchpad/probe_glue_security.py`
(session scratchpad — copy it somewhere durable if it is still needed).

```bash
cd django-glue
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. .venv/bin/python -m pytest \
    /path/to/probe_glue_security.py -c pyproject.toml --rootdir . \
    -p no:cacheprovider -s -q
```

Observed output:

```text
identity honest: 5 tampered: 999
request honest: WSGIRequest spoofed: str
direct filter on excluded field: 422 queryset_filter_validation_error
traversal filter: 200 ['champion']
order_by excluded field: 200 ['champion', 'rookie']
3 passed
```

The essential probe, for durability:

```python
class ProbeGlue(BaseGlue):
    namespace = 'probe_identity'
    owner_id = Glue.attr(identity=True)

    def __init__(self, owner_id):
        super().__init__(name='probe', access=GlueAccess.VIEW)
        self.owner_id = owner_id

    @classmethod
    def _reconstruct_from_policy(cls, policy):
        return cls(policy.identity['owner_id'])

    @Glue.attr(required_access=GlueAccess.VIEW)
    def whoami(self):
        return self.owner_id


# Registered with owner_id=5, then called with
# state={'owner_id': {'value': 999}} -> whoami() returns 999.
```

The template-context finding was verified standalone against Django 5.2.17:

```python
t = engines['django'].from_string("staff={{ user.is_staff }} perm={{ perms.app.delete_x }}")
t.render({}, request)                                    # staff=False perm=False
t.render({'user': {'is_staff': True},
          'perms': {'app': {'delete_x': True}}}, request)  # staff=True perm=True
```
