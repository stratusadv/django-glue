# Changelog for Django Glue

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