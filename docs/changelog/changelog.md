# Changelog for Django Glue

## v1.0.1

### Fixes

- **Searching a relation field no longer discards choices set via `overrideChoices()`.**

## v1.0.0

### Breaking

Django Glue v1.0.0 is a complete rewrite of the library and is **not compatible with any previous v0.x release**. The entire backend, wire protocol, and JavaScript client were re-architected around a declarative, proxy-based API. All public APIs changed and existing code WILL require migration. The full migration guide is at the bottom of this entry.

### Features

#### Declarative Glue API (Python)

- **Central `Glue` class**: all shortcuts live on a single importable object. Replace `import django_glue as dg` with `from django_glue import Glue`.
- **Shortcuts for every proxy type**:
  - `Glue.model()` – bind a single Django model instance
  - `Glue.queryset()` – bind a QuerySet collection
  - `Glue.form()` – bind a Django `Form` / `ModelForm`
  - `Glue.formset()` – bind a Django `BaseFormSet`
  - `Glue.template()` – bind a Django template by name
  - `Glue.function()` – bind a Python callable by dotted import path
  - `Glue.sequence()` – group multiple glued objects together
  - `Glue.object()` – register any custom `BaseGlue` subclass directly
- **Per-call `access` enforcement**: `GlueAccess.VIEW` / `CHANGE` / `DELETE` with a permission cascade (`DELETE > CHANGE > VIEW`), checked server-side on every request.
- **Loading strategies**: `Glue.model()`, `Glue.queryset()`, etc. accept `loading_strategy=` with `LoadingStrategy.LAZY` (default, fetched on first frontend access), `EAGER` (state included in the initial page manifest), or `INHERIT`.
- **`Glue.choices()`**: declare server-owned choice sources for relation fields with optional `search_fields`, `search_limit`, and rich `fields`. Static Django choices stay local; queryset sources support search with bounded results and no unfiltered collection is ever sent to the client.

#### Declared attributes & custom glue objects

- **`@Glue.attr` / `Glue.attribute`**: descriptor-backed declared attributes on custom glue objects and glued Django objects. Callable attributes support keyword parameters and can expose full proxy manifests (`is_glue_manifest: true`) back to the frontend.
- **`Glue.html_attr` / `render_as_html=True`**: declare an attribute that renders a `TemplateResponse` / `GlueTemplateResponse` to HTML and returns it directly (with a ride-along `manifest_list`), instead of JSON.
- **`Glue.property`**: expose read-only Python properties on custom glue objects, with optional `identity=True` for reconstruction identities.
- **Custom `BaseGlue` subclasses**: default identity, state, and metadata handling plus attribute defaults and factories, minimizing boilerplate for reconstructable custom glue objects.
- **Sequence attribute inference**: assigning a plain list of already-glued items to a `Glue.attr([])` attribute auto-wraps it in a `SequenceGlue`; pass `glue_factory=` to also convert raw items on assignment.
- **Queryset custom attributes**: `@Glue.attr` methods declared on a custom `QuerySet` subclass are discovered by `Glue.queryset()`, bound to the exact already-filtered queryset.
- **`computed_attributes`**: expose read-only Python-computed values (including callables with keyword arguments) on glued model and queryset state.
- **Attribute state controls**: each declared attribute controls which client state is sent back to the server and whether a call refreshes client state.

#### Forms, models & relations

- **Form-driven persistence**: `Glue.model()` and `Glue.queryset()` accept `form=` / `forms=` (instance or class) so field validation, coercion, and saving go through Django forms; per-field errors are returned to the frontend.
- **Field filtering**: `fields=` / `exclude=` (or `'__all__'` / the exported `ALL_FIELDS`) restrict which model fields are exposed, and `select_related=` preloads ForeignKey relations on model/queryset glue.
- **`related_field_config`**: control which fields are exposed on related objects (ForeignKey, OneToOne, reverse FK, ManyToMany).
- **Related set proxies**: reverse foreign-key and many-to-many relations are exposed as nested, read-only queryset proxies. Prefetched relations load eagerly; others load on demand, with cycle detection for nested relationships.
- **Formset Glue**: `Glue.formset()` / `FormSetGlue` bind a Django `BaseFormSet` with support for `append()`, `pop()`, and `validate()` client-side; per-form state is sent to the server under `form_list` on save.
- **Choices override**: `overrideChoices()` / `clearChoicesOverride()` on relation fields for dependent / cascading choice fields, without the default cache-backed getter overwriting the override on the next read.
- **Lazily loaded choices**: foreign-key and M2M choices load on demand via `choices()` with built-in caching to prevent duplicate requests.
- **Binary fields**: binary fields are excluded from the exposed field set by default (and byte objects handled in the encoder); requesting them explicitly raises a clear error.

#### QuerySet pagination

- **Seek (keyset) pagination**: `Glue.queryset()` fetches rows in server-side batches using seek pagination instead of a numbered-page `Paginator`. Every query returns one `DJANGO_GLUE_QUERYSET_BATCH_SIZE`-row batch (default 100), so a queryset of 100,000 rows can never be pulled into the browser by a bare `for...of`.
- **Per-queryset `batch_size=`**: override the batch size per queryset, or pass `batch_size=None` to disable batching. The batch size is signed into the policy token, so the client cannot widen it.
- **Stable seeking**: unordered querysets are ordered by `pk` before seeking; `pk` is always forced on as a final tiebreaker even for a non-unique explicit `order_by`. Each batch is fetched with `field > last_seen_value` instead of `OFFSET n`, so cost is independent of scroll depth.
- **`loadMore()` / `hasNext` / `batchSize`**: the client appends the next batch for infinite scroll; `items`, `hasNext`, and `batchSize` describe what is currently loaded. Each of `filter()`, `orderBy()`, and `slice()` starts an independent seek sequence.
- **Opt-in totals**: computing a total always costs a real `COUNT(*)`, so it is never bundled in by default. `await queryset.count()` runs one on demand for the current filter; `all({withTotal: true})` (or `query_with_params(with_total=True)`) folds a single `COUNT(*)` into the first batch request. `queryset.total` holds the most recent value and survives `loadMore()`.
- **Bounded slicing**: `slice({start, stop})` narrows the queryset like `queryset[start:stop]` but its width cannot exceed `batch_size` on a fresh query, or however many rows a real sequence of batch fetches has covered (tracked server-side in the signed policy). Oversized one-shot windows are rejected with `GlueQuerySetSliceValidationError`.

#### Security & architecture

- **Signed policy tokens**: proxies are authorized with signed, client-held policy tokens instead of being stored in the session. The token carries `session_id`, `request_user_id`, `name`, `namespace`, `identity`, `access`, `attributes`, and `created_at`; the backend verifies the signature and reconstructs the authoritative policy for every request. This removed the session proxy registry, keep-alive polling, and middleware-based expiration.
- **Policy renewal**: policies renew on every attribute call rather than only when client state is updated, keeping an active proxy from expiring out from under continued use. `DJANGO_GLUE_PROXY_POLICY_MAX_AGE_SECONDS` (default 24 hours) bounds token lifetime.
- **Pydantic request validation**: all incoming requests are validated with Pydantic models; action requests are normalized to multipart form data for predictable processing.
- **Explicit exception hierarchy**: `GlueError` and its subclasses (`GlueRequestError`, `GlueAccessError`, `GlueMissingAttributeError`, `GlueInvalidAttributeError`, `GlueModelInstanceNotFoundError`, `GlueQuerySetFilterValidationError`, `GlueQuerySetCursorValidationError`, `GlueQuerySetSliceValidationError`, `GlueInvalidPolicyError`, `GlueInvalidSessionError`, `GlueInvalidUserError`, `GlueExpiredPolicyError`, `GlueCalledStateAttributeError`, `GlueAttributeCallError`), each storing its parameters for programmatic access.
- **QuerySet filter validation**: filters are validated against allowed fields, preventing access to restricted model fields.
- **Custom actions receive the `request` and named parameters**, and are resolved by dotted import path on every call.
- **RCE hardening**: queryset serialization was patched against a pickling vulnerability; serialized data never leaves the server.
- **Message & response helpers**: `Glue.Response`, `Glue.RedirectResponse`, and `GlueMessage` (`debug` / `info` / `success` / `warning` / `error`) for returning structured results to the client.

#### Frontend (JavaScript)

- **Rewritten ES-module client** built with Bun's native bundler (`Bun.build()`), distributed as `django_glue.js` and `django_glue.min.js`.
- **Direct property access**: access proxies directly under typed namespaces on the global `Glue` instance – `Glue.model.obj`, `Glue.querySet.objs`, `Glue.form.my_form`, `Glue.formSet.group`, `Glue.sequence.days`, `Glue.template.card`, `Glue.function.calc` – instead of instantiating classes.
- **Native field getters/setters**: read and write model/form fields as regular properties with automatic change tracking; `$fields` exposes per-field metadata (`label`, `required`, `errors`, etc.).
- **Iterable querysets**: `Symbol.iterator` support for `for...of` loops (iterate `.all()` / `.queryWithParams()` in Alpine).
- **Automatic lazy loading**: model proxies fetch on first field access if not already loaded; `_loading` / `_loaded` track async state.
- **QuerySet child proxies**: each item is a full model proxy with its own `save()` / `delete()`, a `_parent` reference that refreshes on child mutation, and events that bubble to the parent queryset. Annotated fields on querysets are accessible from the frontend, and related models can be expanded inline.
- **Query building**: chainable `filter()`, `orderBy()`, `slice()`, plus `queryWithParams({...})`, `all({withTotal})`, `refresh()`, `prependNew()` / `appendNew()`, `get(pk)`, `new()`, `count()`, `isEmpty`, and `isLoaded`.
- **Shared query cache**: `filter()` / `orderBy()` / `slice()` proxies are cached by their merged parameters across the whole chain (bounded to 64 entries), so `qs.filter(a).orderBy(b)` and `qs.orderBy(b).filter(a)` are the same proxy and a query referenced inside a reactive getter does not refetch forever.
- **Form proxies**: `validate()` and `save()` with automatic `FormData` handling for file uploads and per-field error tracking (`hasErrors(fieldName)`).
- **FormSet proxies**: manage formsets with `append()`, `pop()`, and `validate()`.
- **Template proxies**: server-side HTML rendering with `renderInnerHtml()`, `renderOuterHtml()`, `renderInsertAdjacentHtml*()` and context merging (backend defaults overridden per call).
- **Function proxies**: exposed as a callable that takes a keyword-arguments object matching the Python signature; signatures are extracted via `inspect.signature()`.
- **GlueView**: server-side HTML fragment rendering of any URL via `Glue.view(url)` with `get()` / `post()` / `render*()`; rendered views ride along with any newly registered proxies as a `manifest_list`.
- **Event listeners**: `before`, `after`, and `error` events on proxies (`addListener` / `removeListener` / `clearListeners`), plus global `onMessage` / `onError` handlers on the client.
- **Config**: `config.requestTimeoutSeconds` (default 30) and URL configuration; bundle-cache busting via a content-hashed `?v=` asset version so a rebuilt bundle is never served from cache.
- **Namespace registry is enumerable**: `Object.keys(Glue.querySet)` lists registered names.

#### Template tags

- `{% django_glue_init %}` injects the CSRF token, the versioned script tag, the proxy manifest list, and client configuration.
- `{% js_url %}` generates JavaScript URL expressions from named URLs, walking the resolver to support instance-namespaced apps; with `template_literal=True` it emits `` `.../${param}/...` `` template literals.

### Changes

- **Query result shape**: `query_with_params()` returns `{items, seek_key, has_next, batch_size}` (plus `total` when requested) instead of `{items, total, page, page_size, page_count}`. There is no numbered `page` / `page_count`.
- **Function proxy calling convention**: functions are called with a keyword-arguments object instead of positional arguments.
- **Template and function shortcuts are VIEW-only**: the `access` kwarg was removed from them.
- **Readonly model fields** are exposed on model proxies, and **date/datetime fields are parsed into JavaScript `Date` objects** client-side.
- **Declared attribute behavior**: a plain `TemplateResponse` is rendered and returned as raw text by default; opt in to HTML-coercion with `@Glue.attr(render_as_html=True)` or `Glue.html_attr`.
- **Manifest classification**: callable results are converted to proxies only when explicitly marked `is_glue_manifest: true`, so ordinary objects with manifest-like fields are not misclassified.
- **Failure retry**: a failed lazy `load_state` request is retained on the proxy and can be retried explicitly with `retryLoad()` instead of retrying continuously on every field read.

### Fixes

- **Infinite refetch inside an Alpine getter**: a `filter()` referenced in a reactive getter recreated a fresh unloaded proxy on every re-evaluation; fixed by the shared chained-query cache.
- **Foreign key state round trip**: nested glued forward relations (`red_corner` object plus `red_corner_id`) lost the key when echoed back; the attname state wins and a nested manifest is read by its pk field.
- **Nested lazy related sets**: related sets created on eager rows were built as eager proxies with no state, so `gorilla.skills.all()` resolved to nothing; nested proxies now follow their own `lazy` metadata.
- **Form identity with an empty file field**: iterating an unsaved `FieldFile` while sorting iterable initial values raised an error; only querysets, lists, tuples, and sets are sorted now.
- **Stale / out-of-order search responses**: `searchChoices()` ignores stale responses and `clearSearch()` retains already-selected rich choices for both single and multiple relation fields.
- **`**kwargs` on `@Glue.attr` methods**: `*args` / `**kwargs` parameters were treated as required arguments named `args` / `kwargs` and rejected every call.
- **Valid policies rejected after browser normalization** (e.g. decimal `0.0` becoming `0`); policy signing now uses the same encoder as response serialization.
- **Form choice data corruption**: form fields with model choice data getting corrupted or rejected, and `FormFieldAttribute.get()` now falls back to `field.initial`.
- **Queryset refresh** now marks every proxy in the chain unloaded and reloads, so a list re-fetches after a create/delete elsewhere.
- **Adjacent-HTML rendering methods** on template proxies / GlueView were restored.
- **Registered `onError` handlers**: exceptions are rethrown after invoking the handler so callers can still observe the failure.
- **Queryset clone behavior**: filtered/sorted clones issue real backend queries instead of reusing parent state; filtered, ordered, and sliced queries no longer reuse an eagerly loaded unfiltered result.
- **FormSet registration**: `FormSetGlue` is registered in the server-side glue class registry so `formSet`-namespaced calls resolve correctly.
- **Bundle cache busting**: a rebuilt bundle is never served from the browser cache under an unchanged package version.
- **`Glue.<namespace>` enumerable**: `Object.keys(Glue.querySet)` lists registered names.
- **`js_url` / `{% django_glue_init %}`**: template tags resolve app namespaces even when the URLconf is mounted under a different instance namespace.

### Removed

- **Session-based proxy storage and keep-alive system**: the proxy session registry, keep-alive polling, session-data endpoint, and middleware-based expiration were replaced by signed policy tokens that renew on each call.
- **Module-level shortcut functions** (`import django_glue as dg`); use the central `Glue` class.
- **Frontend field configuration APIs and field templates** (migrated to `django_spire`): glued objects inherit field properties from the backend model or form class.
- **Unique name encoding system** and **global AJAX utility functions**.
- **`DJANGO_GLUE_KEEP_LIVE_*` settings**, replaced by `DJANGO_GLUE_PROXY_POLICY_MAX_AGE_SECONDS` (default 86400 seconds / 24 hours).

### Settings

`DJANGO_GLUE_SESSION_PROXY_KEY`, `DJANGO_GLUE_PROXY_POLICY_MAX_AGE_SECONDS`, `DJANGO_GLUE_VIEW_MAX_REDIRECTS` (default 10), `DJANGO_GLUE_REQUEST_TIMEOUT_SECONDS` (default 30), `DJANGO_GLUE_QUERYSET_BATCH_SIZE` (default 100). Any default in `django_glue.settings` can be overridden by defining the same name in your project's `settings.py`.

### Migration Guide (from v0.x)

#### In views / Python

- Import `from django_glue import Glue` and use `Glue.model(...)`, `Glue.queryset(...)`, `Glue.form(...)`, `Glue.formset(...)`, `Glue.template(...)`, `Glue.function(...)`, and `Glue.sequence(...)` instead of the old module-level shortcuts.
- The glued object kwarg is uniformly named `target` in every shortcut.
- URL inclusion is now `url_patterns += django_glue_urls()`, and the endpoints changed:
  - POST `/__dg__/callable_attribute/<name>/<attr>/` executes a proxy operation
  - POST `/__dg__/glue_view/` renders another Django view as a fragment

#### In templates / JavaScript

- `{% glue_init %}` is now `{% django_glue_init %}`.
- Access glued objects directly by unique name under the type-specific namespace (`Glue.model.<name>`, `Glue.querySet.<name>`, etc.) instead of `new ModelObjectGlue(<name>)` / `new QuerySetGlue(<name>)`.
- Field metadata moved from `obj.glue_fields.field.label` to `obj.$fields.field.label`.
- Action names changed: `update()` → `save()`, `null_object()` → `new()`, `filter()` → `queryWithParams({...})` (individual items use `obj[index].save()` / `obj[index].delete()`).
- QuerySet items are now full model proxies with their own `save()` / `delete()`.
- The old `django_glue_dispatch_response_event()`-style events are replaced by `addListener('save', cb, 'after')` with `before` / `after` / `error` types.

#### Architecture notes

- The old handler system (`GLUE_TYPE_TO_HANDLER_MAP`) was replaced by a unified proxy pattern with `@action` — now declared attributes — on classes.
- Session dataclasses were replaced with Pydantic models; request URLs are now per-object/per-operation.
- Context data is carried on the request object / manifests, not stored in the session.

## Archived

Prior v0.x release notes are preserved in [archived_changelog.md](./archived_changelog.md).
