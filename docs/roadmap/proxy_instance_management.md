# Proxy Instance Management

From the `braydenc/queryset-pagination-and-scrolling-performance` review
(2026-08-27).

## Decision

**`Glue.<namespace>.<name>` builds a new proxy on every property access.** The
singleton registry introduced on the pagination branch (`client._proxies`,
`_resolveProxy`, `_updateProxy`) is reverted before merge, along with the
`reactiveSelf()` helper in `client_js/src/utils.js`. The shared query cache in
`queryset.js` and the `enumerable: true` fix on the registry properties stay.

The one defect this leaves -- a resolved proxy not picking up a later
`loadManifests()` -- is tracked as **GLUE-93** and fixed separately.

## Why

How should `Glue.<namespace>.<name>` behave on repeated access? Two designs were
on the table, each with a real defect:

| | per-access construction (**chosen**) | singleton registry (rejected) |
|---|---|---|
| `Glue.model.gorilla === Glue.model.gorilla` | `false` | `true` |
| Held reference sees `loadManifests()` updates | **no -- stale** | yes, patched in place |
| Cross-scope coupling between `x-data` scopes | none | implicit, invisible at the call site |

## Why per-access construction exists

Proxies were deliberately constructed on every property access so they would be
built *after* Alpine's `initTree`, guaranteeing Alpine wraps them in its reactive
proxy. The intended idiom is to resolve once into `x-data` and hold that
reference:

```html
<div x-data="{ gorillas: Glue.querySet.gorillas }">
```

An earlier refactor of Glue used a global instance map and moved away from it for
this reason.

## Why the branch changed it

Accessing a proxy directly inside an Alpine getter -- rather than assigning it to
`x-data` -- constructed a fresh, unloaded proxy on every reactive re-evaluation,
causing an infinite refetch loop:

```js
get options() { return Glue.querySet.specimens.filter(filter) }
```

The branch fixed this with a `client._proxies` Map plus `_updateProxy()`, and made
`refresh()` reach into Alpine via a `reactiveSelf()` helper
(`globalThis.Alpine?.reactive?.()`), which breaks Glue's framework independence.

**Verified during review:** the infinite loop is fixed by the *shared query cache*
in `queryset.js`, not by `_proxies`. Reverting `client.js` to per-access
construction leaves every queryset and pagination test passing; only four
identity tests in `client.test.js` fail.

## The confirmed defect in per-access construction

A reference held by an `x-data` scope never sees state from a later
`loadManifests()` call (the `Glue.view()` / partial re-render path):

```js
const held = client.model.gorilla          // what x-data holds
client.loadManifests([/* same name, name: 'Renamed' */])

held.name                  // 'Koko'    <- stale
client.model.gorilla.name  // 'Renamed' <- fresh accessor sees the new manifest
```

This affects real templates that bind a proxy in `x-data` and are re-rendered
through a view/partial path, e.g. `gorilla/page/detail_page_partial.html` and
`gorilla/component/gorilla_form_modal.html`.

## Fixing the staleness (GLUE-93)

Keep per-access construction (no stable accessor identity, no implicit
cross-scope coupling), but track handed-out proxies so `_registerManifest` can
patch **live** instances in place when a manifest for the same name arrives.
That is a different data structure than `_proxies` -- a per-name `Set`/`WeakSet`
of issued proxies rather than a single cached instance -- and it fixes the
staleness without making `Glue.x.y === Glue.x.y` true.

## Rejected alternatives

- **Query cache held on `GlueClient`, keyed by proxy name** (so a chained
  queryset stays stable while the base proxy is rebuilt per access): works
  mechanically, but puts queryset-only state and a `_queryCacheFor()` helper on
  the namespace-agnostic client. `client.js` resolves a manifest to a proxy
  class and constructs it; it must not know what any one proxy type does. See
  the layering rules in `AGENTS.md`.

- **Split API** (`Glue.querySet.x` fresh vs `Glue.shared.querySet.x` singleton):
  adds a concept every user must learn, and two similar-but-unequal objects
  invite their own confusion.
- **Framework-agnostic observer hook** (Glue hands out an object passed through
  an injectable `observe()`, with an Alpine adapter supplying
  `Alpine.reactive`): spiked and technically sound -- `this` inside a method is
  the wrapper, wrapping composes to nested proxies and chained clones,
  `defineProperty`/Symbol/`delete`/`instanceof` all survive, cost ~0.03us per
  access. Rejected because it makes cross-scope reactive coupling the *default*,
  which conflicts with Alpine's scope-local model (Alpine offers `$store` for
  deliberate sharing). Also cannot fully protect a reference captured before
  Alpine loads -- and the docs currently teach page-scope patterns
  (`addListener` snippets, the installation example) that would capture one.

## Test impact

Reverting the singleton fails exactly these four in `client.test.js`:

- `named proxies are one shared instance per name`
- `direct namespace proxies are one shared instance`
- `function proxies are one shared instance`
- `re-registering a name updates the existing instance in place`

The first three assert the singleton design itself and would be deleted. The
fourth encodes behavior worth keeping, and should be rewritten to assert that a
*held reference* observes updated state, rather than that the accessor returns
the same object.

## Related

- `client_js/src/client.js` -- `_proxies`, `_resolveProxy`, `_updateProxy`
- `client_js/src/proxies/queryset.js` -- `_queryCache` (the real infinite-loop
  fix), `refresh()`, `_applyResponse()`
- `client_js/src/utils.js` -- `reactiveSelf()`, single call site, to be removed
  with whatever lands here
- `PAGINATION_BRANCH_REVIEW.md` section 3
