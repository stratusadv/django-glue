# Review: `origin/braydenc/queryset-pagination-and-scrolling-performance` vs `master`

> **Note:** This document reviews the branch as originally received. Following this review, we
> reworked the pagination core substantially (offset/Paginator → seek/keyset pagination) and
> renamed several public names. See **"Revisions made during review"** at the bottom for what
> actually shipped -- sections 1 and 10 below describe the *original* implementation this branch
> arrived with, not the final one.

3 commits, 46 files, +3014/-1203 (excluding `uv.lock` and the codegraph db).

1. `3b07b65` Improve performance by adding pagination to QuerySet
2. `a93393a` Update bugs, e2e tests
3. `63a2325` Cache busting

This branch is a clean fast-forward off current `master` (merge-base == `master` HEAD), so everything below is genuinely new on this branch, not rebase noise.

---

## 1. Server-side queryset pagination (the headline feature)

**`django_glue/glue/objects/django/queryset.py`**
- `QuerySetGlue.__init__` gains `page_size: int | None | '__default__'`, resolved by `_resolve_page_size()` (validates positive int, rejects `bool`/non-int/`<1`) and defaulting to the new `DJANGO_GLUE_QUERYSET_PAGE_SIZE` setting (100).
- `page_size` is baked into `get_identity()` → signed into the policy token, so the client can pick a page number but can't widen the page size.
- `get_state()` now returns a full page via the same code path as queries (`_query()`), instead of dumping every row.
- `query_with_params()` gains a `page: int = 1` argument; validated by the new `GlueQuerySetPageValidationError` (422) for non-positive-int values (including `bool`/`float`/`str`/`None`).
- New `paginate(objects, page)` wraps Django's `Paginator`. When `page_size is None`, pagination is skipped but the response still returns the full `{items, total, page, page_size: None, page_count: 1}` shape (page 1 gets everything, any page > 1 gets `[]`).
- New `_ensure_ordered()`: unordered querysets are auto-ordered by `pk` whenever slicing/paging happens, so pages don't skip or repeat rows across requests (a real Django gotcha — LIMIT/OFFSET on an unordered queryset is undefined order).
- **Response shape change**: `query_with_params()` used to return `{items, query: {}}`; now returns `{items, total, page, page_size, page_count}`. This is a breaking wire-format change (see client side).

**`django_glue/glue/attributes/django/model/related_set.py`**
- Prefetched related sets (M2M / reverse FK shown inline on a parent row) are now paginated in-memory via the same `QuerySetGlue.paginate()`, so a gorilla's `.skills` on a list page returns the same `{items, total, page_size, page_count}` shape instead of a bare `{items}`.

**`django_glue/settings.py`**: adds `DJANGO_GLUE_QUERYSET_PAGE_SIZE = 100`.

**`django_glue/exceptions.py`**: adds `GlueQuerySetPageValidationError` (422, mirrors the existing filter-validation error).

---

## 2. Client-side: `GlueQuerySetProxy` becomes page-aware (`client_js/src/proxies/queryset.js`)

This is the biggest single-file change (~166 lines net).

- New reactive getters: `count` (**server total**, not loaded-row count — this is a breaking semantic change, see below), `pageNumber`, `pageSize`, `pageCount`, `hasNext`, `hasPrevious`.
- New `loadMore()`: appends the next page's rows into the *same* proxy instance (for infinite scroll), guarded against concurrent calls (`this.loading`) and against calling past the last page.
- New `refresh()`: marks every proxy in the shared query-cache chain (not just this one) as unloaded, then reloads this one — so a list backed by a filtered/paged proxy still picks up a create/delete elsewhere.
- New `page(n)` / `next()` / `previous()` chain like `filter()`/`orderBy()`/`slice()`.
- **Query cache redesign**: was a plain object keyed by `JSON.stringify(params)` per-instance; now a `Map` **shared across the whole chain** (passed down through `_cloneWithQueryParams`), so `qs.filter(a).orderBy(b)` and `qs.orderBy(b).filter(a)` resolve to the *same* proxy object (params are canonicalized before the cache key is built). Cache is bounded to 64 entries via `_evictQueryCache()` (never evicts the `'{}'` base-query entry or the proxy `this`).
- `filter()`/`orderBy()`/`slice()` now reset `page` to 1 in the merged params (previously they didn't touch page since paging didn't exist).
- New `_seedFrom()` / `options.seed`: a freshly-chained proxy (e.g. `.next()`) is seeded with its source's `_modelProxies`/`_total`/`_pageSize`/`_pageCount` before it has its own data, so the UI shows the *previous* page's rows/totals until the new page's request resolves, rather than flashing empty.
- `_hasQueryParams()` simplified from three explicit checks to `Object.keys(this._queryParams).length > 0` (now also true once `page` alone is set).
- `_applyResponse()` override added so a queryset proxy dropped into the shared-instance-per-name registry (see next section) still resyncs its rows/pagination state when `client.js` calls `_updateProxy`.

---

## 3. Client-side: proxies are now singletons per name (`client_js/src/client.js`)

- New `GlueClient._proxies: Map`. `Glue.model.gorilla` (etc.) used to construct a **new proxy object every property access** via a getter that called `_createProxy()` unconditionally.
- Now: first access creates and caches the proxy (`_resolveProxy`); a later `loadManifests()` call for the same name (e.g. a `Glue.view` re-render) calls the new `_updateProxy()` to patch policy/state/metadata into the *existing* object instead of replacing it.
- This is described in the changelog as a real bug fix: an Alpine getter referencing `Glue.querySet.tasks.filter(...)` was constructing a brand-new, unloaded proxy on every reactive re-evaluation, causing infinite refetch loops.
- Registry properties (`Object.defineProperty(this, namespace, ...)`) gain `enumerable: true` (were previously non-enumerable, so `Object.keys(Glue.querySet)` silently returned nothing).

---

## 4. Nested/related proxy loading-strategy bug (`client_js/src/proxies/base.js`)

- When resolving a nested glue object (e.g. `gorilla.skills`), the nested proxy always inherited the **parent's** `_loadingStrategy`, even when the attribute's own metadata declared `lazy: true/false` explicitly. A related set marked eager-per-field on an otherwise-lazy parent (or vice versa) would get built with the wrong strategy and no state, so e.g. `gorilla.skills.all()` silently resolved to nothing.
- Fix: `nestedLoadingStrategy` now reads `attributeMetadata.lazy` first and only falls back to the parent's strategy when that metadata key is absent.
- Also: an existing cached nested proxy (`proxy[cacheKey]`) is now updated via `_applyResponse()` on every access with fresh manifest state, not just re-pointed at a new policy.

## 5. Alpine reactivity helper (`client_js/src/utils.js`)

- New `reactiveSelf(object)`: wraps an object in `Alpine.reactive()` if Alpine is present, else returns it unchanged. Used by `refresh()` in `queryset.js` to make sure `_loaded = false` on a cached proxy actually triggers an Alpine re-render (mutating a plain, non-reactive-wrapped object wouldn't).

---

## 6. Model foreign-key state round-trip fix (`django_glue/glue/objects/django/model/object.py`)

A real correctness bug fix, independent of pagination:

- Previously, loading client state back onto a forward FK/O2O field only ever looked at `state[field_name]` (the *nested object's* serialized state) and tried to read `.get('value')` off it — but a nested related object's manifest doesn't have a top-level `value` key, so this silently produced `None`/garbage for the FK id in some shapes.
- New `_related_pk_from_state()` handles three shapes in priority order:
  1. `state[field.attname]` (e.g. `red_corner_id`) with a `{'value': ...}` wrapper — wins if present.
  2. `state[field.name]` (e.g. `red_corner`) as a nested manifest dict without a `value` key — pk is read from the nested object's own pk field.
  3. A plain `{'value': ...}` or bare value under `field.name`.
- Also fixes the `field_name not in state` skip condition to check both `field_name` and `field.attname`, since a client echoing only the attname form was previously skipped entirely.
- New test file `test_model_related_state.py` covers all four shapes plus null-clears-the-relation.

## 7. `FormGlue` sort-for-identity fix (`django_glue/glue/objects/django/form/object.py`)

- Old check: `hasattr(value, '__iter__') and not isinstance(value, str) and not hasattr(value, '_meta')` — this is a broad duck-typed check that could catch things it shouldn't (dicts, generators, or in this case an unsaved `FieldFile`, whose `__iter__`/iteration raises `ValueError: The 'x' attribute has no file associated with it` when the file field is empty).
- New check: `isinstance(value, (QuerySet, list, tuple, set, frozenset))` — narrows to the actual collection types the sort logic is meant for.
- Fixes a real crash: an empty file field's "initial" value on a form broke `FormGlue` identity computation entirely.

## 8. `CallableAttribute` variadic-parameter fix (`django_glue/glue/attributes/callable.py`)

- The call-parameter resolver iterated a function's signature and treated **every** non-`self` parameter as required, including `*args`/`**kwargs` — so any `@Glue.attr`-decorated method with a variadic parameter would reject all calls (Python reports `args`/`kwargs` as parameter names for `VAR_POSITIONAL`/`VAR_KEYWORD`).
- Fix: skip parameters whose `kind` is `VAR_POSITIONAL` or `VAR_KEYWORD`.

## 9. Cache-busting for the JS bundle (`django_glue/assets.py` — new file)

- New `asset_version()`: if `django.contrib.staticfiles` is installed and the bundle file is found via `finders.find()`, returns `f'{__VERSION__}.{sha1(bundle_bytes)[:8]}'` (content hash, `lru_cache`'d by mtime), else falls back to the bare package version.
- `django_glue.html` template now does `?v={{ DJANGO_GLUE_ASSET_VERSION }}` instead of `?v={{ DJANGO_GLUE_VERSION }}`.
- Fixes: previously the script tag's cache-busting query param was just the package version string, so rebuilding the bundle without bumping the version (e.g. local dev, or a patch that doesn't touch `constants.__VERSION__`) would keep serving a stale cached bundle from the browser.

## 10. Test-project demo/doc changes

- **New `test_project/lab` app**: `Specimen` model (~100k-row seed via `bulk_create`), `volume_views.py` (seed/clear/view), and `volume_page.html` — a live demo of both new list patterns: an infinite-scroll typeahead (`x-intersect:enter="options.loadMore()"`) and a classic prev/next paged table, both against a queryset registered with `page_size=25` over 100,000 rows.
- **`gorilla/page/list_page.html`**: the inline multi-select "Skills" editor (checkbox dropdown backed by `gorilla.$fields.skills.choices`) was replaced with a read-only badge list bound to the now-paginated `gorilla.skills.items`; `prependNew()` demo button removed; `gorillaQuerySet` converted from a stored value to a getter so filter/order/slice stay live; `x-show="gorillaQuerySet.count === 0"` gained a `!loading` guard (previously showed "no fighters found" flash before the first load resolved, especially visible now that `count` means server total rather than loaded-count).
- **`fight/page/list_page.html`**: `choice.pk`/`choice.__str__`/tuple-destructured choices (`[value, label]`) updated to the `{value, label, obj}` shape. Confirmed this shape already existed in `client_js/src/proxies/fields/choice.js`/`relation.js` on `master` — these templates were simply out of sync with their own existing client API, fixed as a drive-by in the "Update bugs, e2e tests" commit, not a new API introduced by this branch.
- **`base.html`**: adds the `@alpinejs/intersect` CDN plugin (required for `x-intersect` used by the infinite-scroll demo) and an `[x-cloak]` style rule.
- **`components/glue_label.html`**: `{{ glue_field }}.label` → `{{ glue_field_meta|default:glue_field }}.label` (lets a caller point the label at a different field's metadata than the bound field itself — used where `red_corner_id` is the bound field but `red_corner`'s label should show).
- **`docs/guides/query_set_glue.md`**: substantially rewritten. Documents the new pagination model and chain semantics, and **drops several methods from the documented API that turned out to not exist in the actual `master` source** (`queryWithParams()` as a direct client method, `prependNew()`, `appendNew()`, `isEmpty`, `isLoaded`, `_items`) — verified these were already absent from `queryset.js` on `master`, so this is a docs-accuracy fix, not a removal of working functionality.
- **`AGENTS.md`**: corrects a stale settings list (previously documented two settings, `DJANGO_GLUE_KEEP_LIVE_INTERVAL_TIME_SECONDS` / `DJANGO_GLUE_SESSION_EXPIRY_MESSAGE`, that don't match `settings.py`) and updates the `lab/` app description.
- **e2e tests (`test_gorilla_app.py`)**: updated to the new async `.filter().all()` → `{items}` shape (previously `queryWithParams()` returned a bare synchronous array); adds explicit `_wait_for_fighter()` polling before reading fighter cards by name (was previously relying on incidental timing); fixture assertion changed from `any(name.startswith('gorillas__') ...)` to an exact `== ['new_gorilla_model']`.

---

## Suggested review order

1. `django_glue/glue/objects/django/queryset.py` + `test_queryset_pagination.py` — the core server-side pagination logic and its validation edges.
2. `client_js/src/proxies/queryset.js` + `proxies.test.js` — the client proxy rewrite (query cache sharing, `loadMore`, seeding).
3. `client_js/src/client.js` + `client.test.js` — proxy-singleton fix (independent bug fix, worth reviewing on its own merits).
4. `django_glue/glue/objects/django/model/object.py` + `test_model_related_state.py` — FK state round-trip fix.
5. `django_glue/glue/attributes/django/model/related_set.py` — related-set pagination (depends on #1).
6. Smaller independent fixes: `callable.py` (variadic kwargs), `form/object.py` (sort check), `assets.py`/`context.py`/template (cache busting).
7. Test-project/demo changes and docs — lowest risk, mostly illustrative.

---

## Revisions made during review

Reviewing section 1 raised a real concern: `Paginator`-based pagination runs a `COUNT(*)` on
*every* `query_with_params()` call, including ones (like `loadMore()`) that never display a total.
Benchmarked on this repo's own `Specimen`/100k-row demo (SQLite, isolated scratch DB): at 1M rows,
a `Paginator`-based fetch cost ~44ms on a deep page and ~9ms even on a shallow page 2 (almost
entirely the `COUNT`), while a seek-based fetch stayed flat at ~0.3ms regardless of depth or table
size. That gap, not just OFFSET's cost, was the actual justification for reworking the core.

**What changed, relative to sections 1 and 10 above:**

- **Offset paging → seek (keyset) pagination.** `Paginator`/`page`/`page_count` were replaced by
  `GlueCollectionCursor`/`GlueSeekBatch` (`django_glue/glue/objects/django/cursor.py`, new file).
  A batch is fetched via `field__gt`/`field__lt` against the last row's position instead of
  `LIMIT/OFFSET`, with `pk` always forced on as a final tiebreaker (deduplicated) even behind a
  non-unique explicit `order_by`. `has_next` comes from fetching one extra row past `batch_size`,
  never from a `COUNT(*)`.
- **`page_size` → `batch_size`**, **`cursor_key`/`page` → `seek_key`**, **`paginate()` →
  `seek_batch()`** across Python, JS, settings (`DJANGO_GLUE_QUERYSET_PAGE_SIZE` →
  `DJANGO_GLUE_QUERYSET_BATCH_SIZE`), and templates. `page(n)`/`next()`/`previous()`/`pageNumber`/
  `pageCount`/`hasPrevious` are gone entirely -- seeking is forward-only; `filter()`/`orderBy()`/
  `slice()` each start an independent seek sequence.
- **Total count is now a separate, opt-in operation**, not a field bundled into every batch
  response: `QuerySetGlue.count()` (a new `@DeclaredAttribute`) runs a `COUNT(*)` only when
  explicitly called. For the common "show a total next to a live search box" case, `query_with_params(with_total=True)` (client: `all({withTotal: true})`) folds one `COUNT(*)` into the
  *first* batch of a new filter only -- `loadMore()` never requests it, so scrolling stays free of
  count cost. `GlueQuerySetProxy.count`/`total` on the client changed from a synchronous property
  to this explicit async call.
- **`slice()` is now bounded by `loaded_row_count`**, not unlimited: a slice's width can't exceed
  `batch_size` on a fresh query, or however many rows a real sequence of `seek_batch()` calls under
  the same filter/order_by has already covered. This count is tracked server-side, keyed by
  `(filter, order_by)`, and lives in the signed policy identity (`loaded_row_count`,
  `last_query_params`) -- reset to 0 whenever the filter/order_by changes, verified by the server
  rather than trusted from the client, so it can't be inflated to smuggle an arbitrarily large
  one-shot window through `slice()`. Violating it raises `GlueQuerySetSliceValidationError`.
- **The signed policy now renews on every attribute call**, not only when `updates_client_state`
  is true (`django_glue/glue/base.py`) -- needed so `loaded_row_count`'s advance (an identity fact)
  rides back to the client even on read-only calls that don't touch `state`/`metadata`. This is a
  behavior change with its own implication: a live proxy's policy expiry now slides forward on
  every access, the same way an active session would, rather than only on state-mutating calls.
- **`RelatedSetFieldAttribute`** (`related_set.py`) calls the same `seek_batch()`, unchanged in
  spirit from the original branch's in-memory pagination -- just updated to the new response shape.
- **Demo templates** (`volume_page.html`, `gorilla/page/list_page.html`) and the guide
  (`docs/guides/query_set_glue.md`) were rewritten to match: the "paged table" demo became a
  Next-only "batched table" (no page numbers, no `Previous` -- a pure seek cursor has no
  server-side "go back"); the typeahead's total is now fetched once via `all({withTotal: true})`
  and cached in Alpine state rather than read off a synchronous property; `gorillaQuerySet.count`/
  `gorilla.skills.count` were replaced with `.items.length` since a bare row-count check should
  reflect what's loaded, not a server total nobody asked for.

**Not changed:** `django-glue.js`/`.min.js` were rebuilt from source (`bun run build`); no manual
edits went into the compiled bundle. All 93 Python tests and 89 JS tests pass as of the last full
run.
