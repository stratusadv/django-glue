# Changelog for Django Glue

## v1.0.1-rc8

### Features

- **QuerySet pagination**: `Glue.queryset()` now pages its rows on the server. Every query (`all()`, `filter()`, `orderBy()`, `slice()`, and the initial `EAGER` state) returns one page, `DJANGO_GLUE_QUERYSET_PAGE_SIZE` rows long (default 100), so a queryset of 100,000 rows can never be pulled into the browser by a bare `for...of` or `x-for`. Pass `page_size=` to `Glue.queryset()` to size the page per queryset, or `page_size=None` to disable paging for that queryset. The page size is signed into the policy token, so the client cannot widen it. Unordered querysets are ordered by `pk` before slicing so pages are stable. On the client, `page(n)`, `next()`, and `previous()` chain like `filter()`, and `count`, `pageNumber`, `pageSize`, `pageCount`, `hasNext`, and `hasPrevious` describe the loaded page. Prefetched related sets are paged in memory with the same shape. `loadMore()` appends the next page to the same proxy for infinite scroll, and a chained proxy (`page(n)`, `filter()`, ...) shows its source's rows and totals until its own page arrives, so paging swaps rows in place instead of emptying the list.

### Fixes

- **`Glue.<namespace>.<name>` is one shared instance**: the client registry used to build a brand-new proxy on every property access, so `Glue.querySet.tasks.filter(...)` inside an Alpine getter created a fresh, unloaded proxy per render and refetched forever. Each registered name now resolves to a single proxy; a later `manifest_list` carrying the same name (for example from a `Glue.view` render) updates that instance in place instead of replacing it.
- **`Glue.<namespace>` is enumerable**: `Object.keys(Glue.querySet)` lists the registered names; the registry properties were defined non-enumerable.
- **`QuerySetProxy.refresh()`**: marks every proxy in the chain unloaded and reloads this one, so a list re-fetches after a create or delete from another component.
- **`**kwargs` on `@Glue.attr` methods**: the call resolver treated a `*args` / `**kwargs` parameter as a required argument named `args` / `kwargs` and rejected every call.
- **Foreign key state round trip**: a model with a glued forward relation (`red_corner` as a nested object plus `red_corner_id`) lost the key when the client echoed state back, because the nested object's manifest was read as a `{value: ...}` pair. The attname state wins, and a nested manifest is read by its pk field.
- **Nested lazy related sets**: a `related_set` (M2M / reverse FK) on an eager row was created as an eager proxy with no state, so `gorilla.skills.all()` resolved to nothing. Nested proxies now follow their own `lazy` metadata.
- **Form identity with an empty file field**: `FormGlue` sorted every iterable initial value to keep the signed policy stable, which also tried to iterate an unsaved `FieldFile` and raised `The 'profile_photo' attribute has no file associated with it`. Only querysets, lists, tuples, and sets are sorted now.

### Changes

- **`count` is the server total**: `GlueQuerySetProxy.count` is now the number of rows matching the query on the server, not the number of rows loaded into the current page. Use `items.length` for the loaded count.
- **Query result shape**: `query_with_params()` returns `{items, total, page, page_size, page_count}` instead of `{items, query}`.
- **Chained queries share one cache**: `filter()` / `orderBy()` / `slice()` / `page()` proxies are cached by their merged parameters across the whole chain, so `qs.filter(a).orderBy(b)` and `qs.orderBy(b).filter(a)` are the same proxy and `page(1)` is the base query. The cache is bounded to 64 entries. `filter()`, `orderBy()`, and `slice()` reset to the first page.

## v1.0.1-rc7

### Changes

- **`@Glue.attr` no longer auto-coerces a `TemplateResponse` to a `GlueTemplateResponse`**: previously, any plain Django `TemplateResponse` returned from a `@Glue.attr` method was automatically wrapped as a `GlueTemplateResponse` (rendered HTML with a ride-along `manifest_list`). By default it's now just rendered and sent as raw text in the `result` field, like any other plain value. Opt in to the old HTML-coercion behavior with `@Glue.attr(render_as_html=True)`, or the new shortcut `@Glue.html_attr` (same as `@Glue.attr(render_as_html=True)`, accepts the same kwargs). Returning a `GlueTemplateResponse` directly, or calling `GlueTemplateResponse.from_template_response(...)` yourself, is unaffected -- this only changes the implicit coercion of a bare `TemplateResponse`.

### Removed

- **`Glue.json()` removed**: The `Glue.json()` shortcut, the backend `JsonGlue`/`JsonValue`, and the frontend `GlueJsonProxy` (the `json` namespace) have been removed. Serializable dict/list/primitive values should instead be exposed through declared attributes on a custom glue object, or through the type-specific proxies.

## v1.0.1-rc6

### Features

- **Sequence attribute inference**: A `Glue.attr([])` declaration now infers a sequence automatically -- assigning a plain `list` of already-glued (`BaseGlue`) items wraps it in a `SequenceGlue` on the spot, using the attribute's own name and the owning instance's runtime `access`. Pass `glue_factory=` to `Glue.attr(...)` to also convert raw (non-Glue) items on assignment, e.g. `entries: list[TimeEntry] = Glue.attr([], glue_factory=build_time_entry_glue)`. Removes the need to hand-construct a `SequenceGlue` (previously `CollectionGlue`) with a manually kept-in-sync `name=` argument for this common case.
- **Queryset custom attributes**: `Glue.queryset()` now discovers `@Glue.attr`-decorated methods declared directly on a custom `QuerySet` subclass, mirroring how `Glue.model()` already exposes methods declared on the model instance. The method is bound to the exact, already-filtered queryset passed to `Glue.queryset()`, not a fresh unfiltered manager.
- **Glue template responses**: A `@Glue.attr` method can now return a `GlueTemplateResponse` (or a plain Django `TemplateResponse`, coerced automatically) to render a template inline against the current request and return the HTML directly, instead of JSON data. Any `Glue.queryset()`/`Glue.model()`/etc. calls made earlier in the same request -- including by the rendered template itself -- ride along as `manifest_list`, the same way `Glue.view(...)` already does. On the client, the call resolves to a `GlueHtmlResult` with the same `renderInnerHtml()`/`renderOuterHtml()`/`renderInsertAdjacentHtml*()` API as `GlueView`/`GlueTemplateProxy`.

### Changes

- **`CollectionGlue` renamed to `SequenceGlue`**: `Glue.collection()` is now `Glue.sequence()`, and the wire namespace changed from `collection` to `sequence` (client and server must be updated together). `CollectionLazyLoadNotSupportedError` is now `SequenceLazyLoadNotSupportedError`.

## v1.0.1-rc5

### Changes

- **Collection Glue item representation rewritten**: `Glue.collection()` items are no longer represented as individually named nested attributes (`items.0`, `items.1`, ...) walked through the same attribute-path system used for a single object's fixed fields. Items are now carried as a plain array of self-contained manifests under a `state.items` key — the same shape `Glue.queryset()` rows already used — with each item's proxy identity keyed by the item's own name/pk instead of its position in the list.

### Fixes

- Fixed collection items intermittently appearing overwritten, duplicated, or missing on the frontend after adding an item to a collection that reorders on refresh (e.g. sorted by a field other than insertion order). The previous positional attribute naming let an unrelated item's cached proxy get silently reassigned to a different item's identity and data when the collection re-sorted, desyncing what was rendered from the actual (correct) state.

## v1.0.1-rc4

### Changes

- **Signed Policy Tokens**: Glue manifests and callable attribute responses now transport policies as signed tokens. This keeps the signed token as the single source of truth, so harmless browser serialization changes cannot invalidate a policy while the backend still verifies its integrity before authorization. The JavaScript client decodes the token to construct proxies, and the Django backend verifies it and reconstructs the authoritative policy for every request.
- Glue callable results are now converted to proxies only when explicitly marked with `is_glue_manifest: true`, preventing ordinary objects with manifest-like fields from being misclassified.

### Fixes

- Fixed valid Glue policies being rejected after browser-side value normalization changed their visible representation, such as decimal `0.0` values becoming `0`.
- Failed lazy `load_state` requests no longer retry continuously on subsequent field reads; the error is retained on the proxy and can be retried explicitly with `retryLoad()`.

## v1.0.1-rc3

### Features

- **Formset Glue**: Added `Glue.formset()` / `FormSetGlue` for exposing a Django `BaseFormSet` over glue, with a matching `GlueFormSetProxy` on the frontend. Supports `append()`, `pop()`, and `validate()` for managing forms client-side, with per-form state sent to the server under `form_list` on save.
- **Choices Override**: Added `overrideChoices()` / `clearChoicesOverride()` to relation fields, letting a caller explicitly set a field's choices (e.g. for dependent/cascading choice fields) without the default cache-backed getter overwriting them on the next read.

### Fixes

- Registered `FormSetGlue` in the server-side glue class registry so `formSet`-namespaced callable attribute requests resolve correctly instead of failing with a missing-class error.

## v1.0.1-rc2

### Features

- **Loading Strategy**: Added `loading_strategy` parameter to all Glue shortcuts (`Glue.model()`, `Glue.queryset()`, `Glue.collection()`, etc.) for controlling when state is sent to the frontend:
  - `LoadingStrategy.LAZY` (default): State is fetched on first access from the frontend
  - `LoadingStrategy.EAGER`: State is included in the initial page manifest
  - `LoadingStrategy.INHERIT`: Inherit strategy from parent Glue object
- **Collection Glue**: Added `Glue.collection()` for grouping multiple Glue objects together. Collections require `LoadingStrategy.EAGER` — lazy loading is not yet supported.
- **Related Field Configuration**: Added `related_field_config` parameter to `Glue.model()` and `Glue.queryset()` for controlling which fields are exposed on related objects (ForeignKey, OneToOne, reverse FK, ManyToMany).
- **Related Set Proxies**: Reverse foreign-key and many-to-many relationships are now exposed as nested, read-only queryset proxies. Prefetched relations are included eagerly, while non-prefetched relations load on demand, with cycle detection for nested relationships.
- **Custom Glue Objects**: Custom `BaseGlue` subclasses now receive default identity, state, and metadata handling, plus declared-attribute defaults and default factories, reducing the boilerplate required for reconstructable custom Glue objects.
- **Glue Properties**: Added `Glue.property` for exposing read-only properties on custom Glue objects, with optional `identity=True` support for including property values in automatically generated reconstruction identities.
- **Attribute State Controls**: Declared attributes can now control whether all, selected, or no client state is sent to the server and whether an attribute call refreshes client state. Glue manifests returned from calls are automatically converted into frontend proxies.

### Fixes

- Fixed queryset clone behavior so filtered and sorted clones trigger backend queries instead of reusing parent state.
- Fixed queryset caching so filtered, ordered, and sliced queries do not incorrectly reuse an eagerly loaded unfiltered result.

## v1.0.1-rc1

### Features

- Added `computed_attributes` support to `Glue.model()` and `Glue.queryset()` for exposing readonly Python-computed values on glued model state.
- Added support for computed attribute callables with keyword arguments, persisted through Glue policy reconstruction.

### Fixes

- `js_url` can now resolve app namespaces even when the URLconf is mounted under a different instance namespace.
- Declared Glue attributes now raise a clear configuration error when a non-serializable value is exposed without nested Glue attributes.

## v1.0.0-a1

### Breaking

- This version of Django Glue is not compatible with any past version. All public APIs have been updated and WILL require changes in your code. Details of the changes are listed below.

### Features

- **Improved JavaScript API**: The JavaScript client has been completely rewritten with a more ergonomic, intuitive API:

  - **Direct property access**: Access proxy objects directly as properties of the global `Glue` object under type-specific namespaces (e.g., `Glue.model.obj`, `Glue.querySet.objs`, `Glue.form.my_form`) instead of instantiating classes.
  - **Native field getters/setters**: Read and write model fields as regular properties (`Glue.model.obj.title = 'New Title'`) with automatic change tracking.
  - **Field metadata via `$fields`**: Field metadata is exposed through the `$fields` property on each proxy (e.g., `Glue.model.obj.$fields.title.label`, `Glue.model.obj.$fields.title.required`).
  - **Iterable querysets**: QuerySet proxies implement `Symbol.iterator`, allowing `for...of` loops directly over items (doesn't work in Alpine.js, must iterate over `.all()` or `.queryWithParams()`)
  - **Automatic lazy loading**: Model proxies on the frontend automatically fetch data on first field access if not already loaded.
  - **Built-in loading state**: Track async operations via `_loading` and `_loaded` properties on all proxies.
  - **Automatic error tracking**: Per-field error state with `has_errors` and `error_text` properties on each field's data object.
  - **Lazy FK/M2M choices loading**: Foreign key choices are loaded on-demand via async `choices()` method on field data with built-in caching to prevent duplicate requests.
- **QuerySet Child Proxy System**: Items returned from querysets are full `GlueModelProxy` instances:

  - Each item has its own `save()` and `delete()` methods for individual CRUD operations.
  - Child proxies maintain a reference to their parent queryset via `_parent`.
  - Deleting or saving a child automatically refreshes the parent queryset.
  - Child proxy events bubble up to the parent queryset's listeners.
  - Annotated fields on querysets are now accessible from the frontend glue objects.
  - Related models can be expanded their fields can accessed accessed from the parent object in the frontend glue object.
- **QuerySet Query Building**: Chainable methods for building queries on the frontend:

  ```javascript
  // Chain filter, order, and slice operations
  const items = await Glue.querySet.objs.filter({done: false}).orderBy('title').slice(0, 10).all()

  // Or pass all params at once (recommended approach in Alpine.js `x-for` loops to preserve reactivity)
  const items = await Glue.querySet.objs.queryWithParams({
      filter: {done: false, title__icontains: 'urgent'},
      order_by: ['title', '-created_at'],
      slice: {start: 0, stop: 10}
  })
  ```
- **QuerySet Convenience Methods**:

  - `all()` - Fetch all items, uses current internal set of query params (shorthand for `queryWithParams()`)
  - `refresh()` - Clear cache and re-fetch current query
  - `prependNew()` / `appendNew()` - Add a new unsaved item to the start or end of the list
  - `isEmpty` / `isLoaded` - Computed properties for UI state management
- **Form Proxy Support**: New `Glue.form()` shortcut enables binding Django Forms (both regular Forms and ModelForms) to JavaScript with full, end-to-end validation support:

  - `validate()` - Validate form data without saving
  - `save()` - Validate and persist (for ModelForms) or return cleaned data (for regular Forms)
  - Automatic FormData handling for file uploads
  - Per-field error tracking with `hasErrors(fieldName)` helper
- **Template Proxy Support**: New `Glue.template()` shortcut enables rendering Django templates from JavaScript with dynamic context data:

  - Register a template on the backend with `Glue.template(request, unique_name='card', target='components/card.html', context_data={...})`
  - Access on the frontend via `Glue.template.card`
  - Same DOM rendering methods as `Glue.view`: `renderInnerHtml()`, `renderOuterHtml()`, `renderInsertAdjacentHtmlBeforeEnd()`, `renderInsertAdjacentHtmlAfterEnd()`, `renderInsertAdjacentHtmlBeforeBegin()`, `renderInsertAdjacentHtmlAfterBegin()`
  - Context data merges: backend `context_data` defaults are overridden by per-call payload from JavaScript
  - Supports event listeners (`before`, `after`, `error`) on `render_html` action
  - Registered in session with keep-alive, consistent with model/queryset/form proxies
- **Function Proxy Support**: New `Glue.function()` shortcut enables calling Python functions from JavaScript with keyword arguments:

  - Register a function on the backend with `Glue.function(request, unique_name='calculate', target='myapp.utils.calculate_total')`
  - Access on the frontend as a callable: `await Glue.function.calculate({kwarg_1: 100, kwarg_2: 0.08, kwarg_3: true})`
  - Function signatures are automatically extracted via `inspect.signature()` and sent to the client
  - Supports event listeners (`before`, `after`, `error`) on `execute` action
  - Functions are resolved by dotted import path on each request
  - Registered in session with keep-alive, consistent with model/queryset/form proxies
- **Event Listener System**: JavaScript proxies now support `before`, `after`, and `error` event listeners for reactive UI patterns:

  ```javascript
  // Add listeners for any action
  Glue.model.obj.addListener('save', (event) => {
      console.log('About to save:', event.payload)
  }, 'before')

  Glue.model.obj.addListener('save', (event) => {
      console.log('Saved successfully:', event.result)
  }, 'after')

  Glue.model.obj.addListener('save', (event) => {
      console.error('Save failed:', event.error)
  }, 'error')

  // Chainable listener management
  Glue.model.obj
      .addListener('delete', onDelete, 'after')
      .addListener('delete', onDeleteError, 'error')

  // Remove specific listeners
  Glue.model.obj.removeListener('save', myCallback, 'after')

  // Clear all listeners
  Glue.model.obj.clearListeners()
  ```
- **Request Timeout Configuration**: HTTP requests now support configurable timeouts (default 30 seconds) via `config.requestTimeoutSeconds`.
- **Explicit Exception Hierarchy**: New custom exceptions provide clearer error handling:

  - `GlueError` (base)
  - `GlueProxyNotFoundError`
  - `GlueAccessError`
  - `GlueMissingActionError`
  - `GlueModelInstanceNotFoundError`
  - `GlueQuerySetFilterValidationError`
  - `GluePayloadValidationError` (removed — was never raised) (removed — was never raised)
- **QuerySet Filter Validation**: Filters are now validated against allowed fields, preventing access to restricted model fields.
- **Pydantic Request Validation**: All incoming requests are validated using Pydantic models for improved type safety.
- **ES Modules JavaScript Client**: The JavaScript client has been rewritten using modern ES modules, built with Bun's native bundler (`Bun.build()`).

### Changes + Migration

#### In Views/Python

- There is now a central `Glue` class that provides access to all shortcuts and other relevant functionality.

  - It can be imported via `from django_glue import Glue` (instead of `import django_glue as dg`)
  - Shortcut names have been changed:
    - `dg.glue_model_object` -> `Glue.model`
    - `dg.glue_queryset` -> `Glue.queryset`
    - NEW: `Glue.form` for binding Django Forms
  - The kwarg for the object passed to each glue shortcut has been uniformly renamed to `target`
- **URL inclusion changed**:

  - Old: `path('django_glue/', include(django_glue_urls()))`
  - New: the `django_glue_urls()` shortcut can be used to append the URL patterns to your project's URL configuration.
- **Settings names changed**:

  - `DJANGO_GLUE_KEEP_LIVE_EXPIRE_TIME_SECONDS` -> `DJANGO_GLUE_KEEP_LIVE_INTERVAL_TIME_SECONDS`

#### In Templates/JavaScript

- The installation process has been slightly changed.

  - The `{% glue_init %}` template tag has been renamed to `{% django_glue_init %}` to be slightly more descriptive.
- The method of accessing and configuring glued objects has completely changed.

  - Instead of getting the glued object by creating a new instance (e.g. `new ModelObjectGlue(<unique_name>)`, `new QuerySetGlue(<unique_name>)`), you now access them directly using their unique name under the type-specific namespace of the global `Glue` instance (e.g. `Glue.model.<unique_name>`, `Glue.querySet.<unique_name>`, `Glue.form.<unique_name>`)
- Glued objects can no longer have their form/field properties configured on the frontend. They inherit their field properties from the way they are glued in the backend (either from the model or from a custom form class passed into the Glue shortcut). The original purpose of this was largely to tweak the field template behaviour and to compensate for functional gaps in the Glue object data binding process, but now this sort of customization should be done by overriding the field templates instead.
- The method of accessing glued object field meta information has been changed.

  - Old: `obj.glue_fields.field.label` or `obj._meta.field.label`
  - New: `obj.$fields.field.label`, `obj.$fields.field.required`, etc.
- **Action method names changed**:

  - Model objects:
    - `obj.get()` -> `obj.get()` (same)
    - `obj.update()` -> `obj.save()` (renamed)
    - `obj.delete()` -> `obj.delete()` (same)
  - QuerySets:
    - `objs.all()` -> `objs.all()` (same)
    - `objs.filter()` -> `objs.queryWithParams({...})` (renamed to allow batched parameter payloads for filtering, ordering, slicing, etc.)
    - `objs.get(pk)` -> `objs.get(pk)` (same)
    - `objs.update(pk, data)` -> `objs[index].save()` (save individual items)
    - `objs.delete(pk)` -> `objs[index].delete()` (delete individual items)
    - `objs.null_object()` -> `objs.new()` (renamed)
- **QuerySet items are now full proxies**: Each item returned from `Glue.querySet.objs.all()` or `Glue.querySet.objs.queryWithParams()` is a `GlueModelProxy` instance with full `save()` and `delete()` capabilities, rather than plain data objects.
- **Event system replaced**:

  - Old: `django_glue_dispatch_response_event()`, `django_glue_dispatch_object_get_error_event()`, etc.
  - New: `Glue.obj.addListener('save', callback, 'after')` with `before`, `after`, `error` event types

#### Architecture Changes

- **Handler system replaced with Proxy pattern**: The old `GLUE_TYPE_TO_HANDLER_MAP` routing with dedicated handler classes has been replaced with a unified proxy system where actions are methods decorated with `@action`.
- **Dataclasses replaced with Pydantic**: Session data and request/response models now use Pydantic for validation.
- **URL routing updated**:

  - Old: Single `/django_glue/` endpoint with action in request body
  - New: RESTful URLs `/django_glue/<unique_name>/<action>/` allows for more verbose logs allowing for easier debugging
- **Context data storage**: Proxy context data is now stored on the request object (`request.__glue_context_data__`) rather than directly in session, reducing session size.

### Fixes

- **Improved M2M handling**: Many-to-many fields now use `prefetch_related()` to avoid N+1 queries and are properly serialized as lists of PKs.
- **File field handling**: File uploads are now properly deferred until after regular field validation to prevent issues with `upload_to` callables.

### Removed

- Field templates (`django_glue/templates/django_glue/fields/`) - migrated to django_spire
- Frontend field configuration APIs
- Unique name encoding system
- Global AJAX utility functions

### Other Notes

- The JavaScript client is now built using Bun's native bundler (`Bun.build()`) and distributed as both `django_glue.js` and `django_glue.min.js`.
- Tests have been reorganized: Python tests use pytest with pytest-django, JavaScript tests use Bun test with Happy-DOM, and E2E tests use Playwright.
