# Changelog for Django Glue

## v1.0.0-a1

### Breaking

- This version of Django Glue is not compatible with any past version. All public APIs have been updated and WILL require changes in your code. Details of the changes are listed below.

### Features

- **Improved JavaScript API**: The JavaScript client has been completely rewritten with a more ergonomic, intuitive API:
  - **Direct property access**: Access proxy objects directly as properties of the global `Glue` object by their registered unique_names (e.g., `Glue.obj`, `Glue.objs`) instead of instantiating classes.
  - **Native field getters/setters**: Read and write model fields as regular properties (`Glue.obj.title = 'New Title'`) with automatic change tracking.
  - **Auto-generated field metadata properties**: Field metadata is exposed as camelCase properties directly on the proxy (e.g., `Glue.obj.titleLabel`, `Glue.obj.titleRequired`, `Glue.obj.titleMaxLength`).
  - **Iterable querysets**: QuerySet proxies implement `Symbol.iterator`, allowing `for...of` loops directly over items (doesn't work in Alpine.js, must iterate over `.all()` or `.queryWithParams()`) 
  - **Automatic lazy loading**: Model proxies on the frontend automatically fetch data on first field access if not already loaded.
  - **Built-in loading state**: Track async operations via `$loading` and `$loaded` properties on all proxies.
  - **Automatic error tracking**: Per-field error state with `fieldNameHasErrors` and `fieldNameErrorText` properties generated for each field.
  - **Lazy FK/M2M choices loading**: Foreign key choices are loaded on-demand via async `fieldNameChoices()` methods with built-in caching to prevent duplicate requests.

- **QuerySet Child Proxy System**: Items returned from querysets are full `GlueModelProxy` instances:
  - Each item has its own `save()` and `delete()` methods for individual CRUD operations.
  - Child proxies maintain a reference to their parent queryset via `$parent`.
  - Deleting or saving a child automatically refreshes the parent queryset.
  - Child proxy events bubble up to the parent queryset's listeners.

- **QuerySet Query Building**: Chainable methods for building queries on the frontend:
  ```javascript
  // Chain filter, order, and slice operations
  const obj = await Glue.objs.filter({done: false}).orderBy('title').slice(0, 10).all()

  // Or pass all params at once (recommended approach in Alpine.js `x-for` loops to preserve reactivity)
  const obj = await Glue.objs.queryWithParams({
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

- **Event Listener System**: JavaScript proxies now support `before`, `after`, and `error` event listeners for reactive UI patterns:
  ```javascript
  // Add listeners for any action
  Glue.obj.addListener('save', (event) => {
      console.log('About to save:', event.payload)
  }, 'before')

  Glue.obj.addListener('save', (event) => {
      console.log('Saved successfully:', event.result)
  }, 'after')

  Glue.obj.addListener('save', (event) => {
      console.error('Save failed:', event.error)
  }, 'error')

  // Chainable listener management
  Glue.obj
      .addListener('delete', onDelete, 'after')
      .addListener('delete', onDeleteError, 'error')

  // Remove specific listeners
  Glue.obj.removeListener('save', myCallback, 'after')

  // Clear all listeners
  Glue.obj.clearListeners()
  ```

- **Request Timeout Configuration**: HTTP requests now support configurable timeouts (default 30 seconds) via `config.requestTimeoutMs`.

- **Explicit Exception Hierarchy**: New custom exceptions provide clearer error handling:
  - `GlueError` (base)
  - `GlueProxyNotFoundError`
  - `GlueAccessError`
  - `GlueMissingActionError`
  - `GlueModelInstanceNotFoundError`
  - `GlueQuerySetFilterValidationError`
  - `GluePayloadValidationError`

- **QuerySet Filter Validation**: Filters are now validated against allowed fields, preventing access to restricted model fields.

- **Pydantic Request Validation**: All incoming requests are validated using Pydantic models for improved type safety.

- **ES Modules JavaScript Client**: The JavaScript client has been rewritten using modern ES modules, built with esbuild.

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
  - Instead of getting the glued object by creating a new instance (e.g. `new ModelObjectGlue(<unique_name>)`, `new QuerySetGlue(<unique_name>)`), you now access them directly using their unique name as a property of the global `Glue` instance (e.g. `Glue.<unique_name_1>`, `Glue.<unique_name_2>`)

- Glued objects can no longer have their form/field properties configured on the frontend. They inherit their field properties from the way they are glued in the backend (either from the model or from a custom form class passed into the Glue shortcut). The original purpose of this was largely to tweak the field template behaviour and to compensate for functional gaps in the Glue object data binding process, but now this sort of customization should be done by overriding the field templates instead.

- The method of accessing glued object field meta information has been changed.
  - Old: `obj.glue_fields.field.label` or `obj._meta.field.label`
  - New: properties are generated for each meta field name: `obj.fieldLabel`, `obj.fieldRequired`, etc.

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

- **QuerySet items are now full proxies**: Each item returned from `Glue.objs.all()` or `Glue.objs.queryWithParams()` is a `GlueModelProxy` instance with full `save()` and `delete()` capabilities, rather than plain data objects.

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

- The JavaScript client is now built using esbuild and distributed as both `glue.js` and `glue.min.js`.
- Tests have been reorganized: Python tests use pytest with pytest-django, JavaScript tests use Jest with Babel, and E2E tests use Playwright.
- Documentation is now built with MkDocs and hosted at https://django-glue.stratusadv.com.