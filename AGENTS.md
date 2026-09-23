# Django Glue

A library that binds Django models, querysets, forms, and callables to a
JavaScript client. The server builds **Glue objects** whose state is signed
into opaque policy tokens; the client holds one live proxy per wire **address**
and reconciles each response as authoritative.

## Quick Reference

| Item | Value |
|------|-------|
| Python | >= 3.11 |
| Django | >= 5 |
| JS Runtime | Bun |
| License | MIT |
| Package version | `django_glue/constants.py` (`__VERSION__`) |
| Docs | https://django-glue.stratusadv.com |
| Repo | https://github.com/stratusadv/django-glue |

## Design authority

`design/AGENTS.md` governs work on the reactive system (the state-model
refactor). Before editing `django_glue/` or `client_js/` for that work: read
the active phase and its gate in `design/reactive-system/roadmap.md`, then the
governing sections of `design/reactive-system/state-model.md` (and
`component-system.md` for components). This file describes the tree as it is;
where it and the design docs disagree about the target architecture, the design
docs win.

## Project structure

```
django-glue/
├── django_glue/
│   ├── glue/                       # The Glue object system
│   │   ├── base.py                 # BaseGlue: attributes, policy, children, calls
│   │   ├── policy.py               # GluePolicy: signed token, state_snapshot, children
│   │   ├── address.py              # Address derivation
│   │   ├── context.py              # GlueContextManager (page load)
│   │   ├── attributes/             # DeclaredAttribute, definitions, collector, adapters
│   │   ├── objects/django/         # ModelGlue, QuerySetGlue, FormGlue, FormSetGlue
│   │   ├── function.py             # FunctionGlue
│   │   ├── component.py            # Component rendering and lifecycle
│   │   └── operation.py            # GlueOperation authorization records
│   ├── resolver/
│   │   ├── attribute_call/         # /__dg__/callable_attribute/ endpoint (batch entries)
│   ├── middleware.py               # Glue.view response middleware
│   ├── shortcuts/glue.py           # Glue.model/queryset/form/formset/function/...
│   ├── shortcuts/urls.py           # django_glue_urls()
│   ├── access.py                   # GlueAccess (VIEW/ADD/CHANGE/DELETE)
│   ├── response.py                 # GlueResponse, GlueTemplateResponse, render helpers
│   ├── exceptions.py               # GlueError family + closed error-code set
│   ├── serialization.py            # Serializer registry for field values
│   ├── encoders.py                 # JSON encoder for wire values
│   ├── message.py                  # GlueMessage (effects channel)
│   ├── settings.py / conf.py       # DJANGO_GLUE_* settings + loader
│   ├── templatetags/django_glue.py # {% django_glue_init %}, {% glue_component %}
│   ├── templates/django_glue/      # init template (context JSON + client bootstrap)
│   └── tests/                      # pytest suite (glue/, resolver/, e2e/, security/, ...)
├── client_js/
│   ├── django_glue.js              # Entry: globalThis.GlueClient, installs Alpine
│   ├── scripts/build.js            # Bun bundler → django_glue/static/django_glue/js/
│   ├── src/
│   │   ├── client.js               # GlueClient: namespace getters, addressed entry registration
│   │   ├── http.js                 # Multipart attribute requests, file extraction
│   │   ├── policy.js               # Signed-policy-token client
│   │   ├── alpine.js               # The only module that references Alpine/morph
│   │   ├── runtime/                # addressRegistry, addressRecord, attributeMaterializer,
│   │   │                           # childBinder, responseDispatcher, state
│   │   ├── proxies/                # base, model, queryset, form, formset, function,
│   │   │                           # component, sequence, fieldBacked + fields/
│   │   └── view.js                 # Glue.view (server-rendered fragments)
│   └── tests/                      # bun test (happy-dom)
├── test_project/                   # Django app used by all tests (gorilla, fight,
│                                   # comments, lab, core)
├── design/                         # Reactive-system design docs (authority)
├── docs/                           # MkDocs site
├── justfile                        # All dev commands
└── STATE_MODEL_HANDOFF.md          # Working handoff for the state-model branch
```

## Server: Glue objects

### Registration

```python
from django_glue import Glue, GlueAccess, DeclaredAttribute

def list_view(request):
    Glue.queryset(
        request=request,
        target=Gorilla.objects.order_by('-updated_at').all(),
        unique_name='gorillas',
        access=Glue.Access.DELETE,
        fields=['id', 'name', 'description', 'age', 'skills__name'],
    )
    Glue.form(request=request, target=GorillaForm(), unique_name='new_gorilla_form',
              access=Glue.Access.CHANGE)
    Glue.model(request=request, target=Gorilla(), unique_name='new_gorilla_model',
               access=Glue.Access.CHANGE, exclude=['signature'])
    Glue.function(request=request, unique_name='calculate_total',
                  target='myapp.utils.calculate_total')
    return render(request, 'gorilla/page/list_page.html')
```

Each call builds a Glue object and adds it to the request's
`GlueContextManager`; `{% django_glue_init %}` then serializes addressed
entries into the page. `Glue.object(request, glue=...)` registers custom
`BaseGlue` subclasses. `Glue.formset` and `Glue.choices` cover keyed forms
and choice sources (`django_glue/shortcuts/glue.py`).

Hierarchy:

```
BaseGlue (django_glue/glue/base.py)
├── ModelGlue       (glue/objects/django/model/object.py)
├── QuerySetGlue    (glue/objects/django/queryset.py)
├── FormGlue        (glue/objects/django/form/object.py)
├── FormSetGlue     (glue/objects/django/formset.py, via BaseCollectionGlue)
├── FunctionGlue    (glue/function.py)
└── Component       (glue/component.py)
```

### Declared attributes

`@DeclaredAttribute` is the only client-callable surface — there is no `@action`
decorator and no action registry. A Glue class declares:

- **value attributes** with a `GlueValueRole` — `EDITABLE_STATE` (client writes
  round-trip in `updates`) or `COMPUTED` (down-only `computed_data`),
- **child attributes** declaring the expected Glue type (and nullability),
- **callables** with `required_access`, `allowed_arguments`, and an optional
  Glue return type:

```python
@DeclaredAttribute(required_access=GlueAccess.CHANGE)
def save(self) -> dict[str, Any]:
    self.instance.full_clean()
    self.instance.save()
    return {'pk': self.instance.pk}
```

### Identity, state, authorization

- **Identity** is a signed policy token (`glue/policy.py`): address, name,
  namespace, access, admitted capabilities, the signed `state_snapshot`, and
  the signed `children` map. Lifetime is fixed at
  `DJANGO_GLUE_PROXY_POLICY_MAX_AGE_SECONDS` (default 86400, 24 h) from
  issuance; a successor token with fresh issuance is delivered only when
  retained values change (ADR 013). The token is session-bound and
  re-authorized on every request. Nothing about a Glue object lives in the
  session; there is no keep-alive and no proxy registry.
- **Down-only data** is split: `static_data` (field descriptors with
  `value_path` mappings, child slots, callable schemas — client-forgets,
  stable) and `computed_data` (re-derived output). Responses omit what did not
  change; **omission means the client's previous value stands** — it never
  means "empty".
- **Authorization** is re-checked on every request against the signed policy,
  using `GlueOperation` records (`glue/operation.py`). `GlueAccess` is a
  `StrEnum` with the cascade VIEW < ADD < CHANGE < DELETE.
- **Update admission**: incoming `updates` are checked field-by-field against
  the signed `state_snapshot` and the editable projection before anything is
  applied.

## Wire format (state-model.md §10)

One Glue endpoint, namespace `__dg__` (`django_glue/urls.py`):

| Endpoint | Purpose |
|---|---|
| `POST /__dg__/callable_attribute/` | Attribute calls. Multipart body with a JSON `objects` field — `[{address, policy_token, updates, call: {attribute, kwargs}}]` — plus file parts keyed by update path. Response: `{objects: [entry, ...]}`. |

`Glue.view(url)` requests the real Django URL with Glue content negotiation;
`django_glue.middleware.GlueViewResponseMiddleware` packages the rendered
response and its introduced entries.

Response entries:

- the **addressed entry** carries `address` + `policy_token` / `static_data` /
  `computed_data` (each omitted when unchanged) + `result` +
  `effects: {messages: [...]}`;
- **newly introduced children** ride as their own entries;
- a **failed address** is an entry `{address, error: {code, message}}` that
  advances nothing while every other entry in the batch advances as if it had
  travelled alone;
- an **envelope fault** (malformed `objects`, empty batch, duplicate
  addresses, outer address that doesn't match its signed policy) is a
  whole-response error with no `objects`.

A callable that returns a Glue object has a wire `result` that is the
object's **address** (the callable schema in `static_data` marks it as a Glue
return); the object's entry is included when newly introduced.

## Client

`window.Glue` is a `GlueClient`, created by the `{% django_glue_init %}`
template from the page context. It exposes one proxy per registered name and
`Glue.view(url)`:

```js
const gorilla = Glue.model.gorilla          // ModelGlue proxy
gorilla.name = 'Moses'
await gorilla.save()

const all = await Glue.querySet.gorillas.all()
await all.items[0].save()

const validation = await Glue.form.new_gorilla_form.validate()
const total = await Glue.function.calculate_total({a: 1, b: 2})
await Glue.view('/gorilla/detail/').renderInnerHtml('#panel')
```

- `client_js/src/runtime/` owns the state model: the address registry
  (one `addressRecord` per address), the attribute materializer, the child
  binder, and the response dispatcher that applies each response as
  authoritative (capture request → introduce entries → reconcile → bind →
  resolve result → apply effects).
- `client_js/src/proxies/` holds the per-namespace proxy classes;
  proxy-specific behavior (chaining, caching, hydration, row lists) lives on
  the subclass, never in `base.js` or `client.js`.
- `GlueClient` stays namespace-agnostic: it resolves a namespace to a proxy
  class and constructs. The one `namespace === 'function'` check is a known
  wart, not a precedent.
- Alpine.js enters through `client_js/src/alpine.js` only; everything else
  imports `reactive()`/`morph()` from it. The bundle exposes `window.Alpine`
  and starts it; consuming apps never load a separate Alpine or call
  `Alpine.start()`.

## Development

**Always use `just`** — it loads `development.env`, which the test settings
require. `just --list` shows every recipe; the gates are:

| Task | Command |
|------|---------|
| Python tests (unit) | `just test` (pytest, `-m "not e2e"`) |
| One test file/pattern | `just test-app django_glue/tests/glue/test_formset.py` |
| E2E (Playwright via pytest) | `just test-e2e -x -q` (sets `DJANGO_GLUE_RUN_E2E=1`) |
| JS tests | `just js-tests` (bun test, happy-dom) |
| Build JS bundle | `just js-build` (outputs to `django_glue/static/django_glue/js/`) |
| Dev server | `just run-server` |
| Migrations | `just make-migrations` / `just migrate` |
| Docs build (strict) | `just docs` |

**Run the gates after any change, before finishing:** Python changes →
`just test`; JS changes → `just js-build` then `just js-tests`; both → all
three. `ruff check` / `ruff format` for Python style (see `ruff.toml`); the
pre-existing `ruff --select F` findings are a known baseline — don't add new
ones.

Setup: `.venv` with `pip install -e ".[development]"` (the justfile invokes
`.venv/bin/python` directly), `just js-install` for Bun dependencies; `uv.lock`
tracks the uv alternative.

## Testing

- **Python**: pytest + pytest-django, `django.test.TestCase` subclasses,
  `test_{action}_{condition}` naming. E2E tests are marked `e2e` and only run
  under `DJANGO_GLUE_RUN_E2E=1` (the justfile recipes set it).
- **JS**: `bun test` with happy-dom; tests live in `client_js/tests/` with
  shared fixtures in `testUtils.js`.
- **Test project**: `test_project/` is a real Django app (gorilla, fight,
  comments, lab for volume/morph, core for template tags). All E2E and most
  server tests drive it; its pages and models are fixtures, not examples to
  copy verbatim.

## Security

- The client never sees Glue object internals: identity is the signed policy
  token, state travels as the client-computed `updates` diff checked against
  the signed snapshot, and file uploads ride multipart parts.
- CSRF protection is enforced on both endpoints; the JS client injects the
  `X-CSRFToken` header.
- QuerySet internals may cross the Python boundary via the internal unpickler
  (`glue/queryset_unpickler.py`); nothing untrusted is deserialized.

## Python value types

- Prefer `@dataclass(frozen=True, slots=True, kw_only=True)` for immutable
  structured records.
- Prefer `StrEnum` over `string` `Literal` unions for named runtime domains.
- Use `TypedDict` / `Literal` when the contract is intentionally
  dictionary-shaped or needs static typing only.
