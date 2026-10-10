# Changelog for Django Glue

## v1.3.0

### Features

- A Django view decorator can guard a component from `is_authorized()`, applied
  with `method_decorator` (ADR 033):

  ```python
  @method_decorator(permission_required('entries.view_entry'))
  def is_authorized(self, request, operation):
      return True
  ```

  The rule then covers the page load, a `{% glue_component %}` stamp and every
  later call, and the URL pattern no longer needs `as_view()` wrapped in the
  decorator. A page load the decorator denies responds the way the decorator
  answered, so `login_required` redirects to the login page.

- `$dispatch(name, detail)` raises one of an object's declared events from the
  browser, with no call to the server. It reaches the object's `$on()`
  listeners, the DOM event from a component's root, and any component that
  re-renders on or listens for the event, and makes a request only for the
  last. See [declared events](../guides/advanced/event_listeners.md).

- An error on one object's call carries the same `status` and `details` as an
  error that fails a whole request. On the client they are `error.status` and
  `error.details` on the `GlueAddressError` the call rejects with, so a handler
  can tell a missing row from a denial without matching on the code.

### Changes

- The client is written in TypeScript. The bundle keeps its path
  (`django_glue/js/django_glue.js`), its globals and its API, so a project
  using it changes nothing. Its source moved from `.js` to `.ts` files under
  `client_js/`, with the wire format it shares with the server described in
  `client_js/src/wire.ts`. `just js-typecheck` checks it, and CI runs the
  check before building the bundle.

### Fixes

- An error of status 500 or above on one object's call no longer sends its own
  message to the browser unless `DEBUG` is on. It sends "An unexpected Glue
  server error occurred.", as a failed request already did.

- `is_authorized()` authorizes only by returning `True`. Glue accepted any
  truthy value, so a view decorator placed on the method, which answers a
  denial with a redirect response, authorized the request it meant to deny.
  A response returned from `is_authorized()`, or `PermissionDenied` raised
  from it, is now a denial.

  An `is_authorized()` that returns something other than `True`, `False` or a
  response now raises `TypeError`. Return a boolean, for example
  `return owner is not None` in place of `return owner`.

- Verifying a model parameter no longer raises `RecursionError` when its
  initializer loads a one-to-one with `select_related`. Django caches each side
  of a one-to-one on the other, and the check that names what a supplied row is
  missing followed that loop without end. It affected only requests that verify
  model parameters: `DEBUG`, or `DJANGO_GLUE_VERIFY_MODEL_PARAMETERS = True`.

## v1.2.2

### Breaking

- A component in a directory inside a `components` package is stamped with that
  directory in its tag (ADR 032): a class in `app/components/cards/fancy.py` is
  `app/cards/fancy`, where it was `app/fancy`. Glue no longer searches the
  directories below the package a tag names, so the old tag raises
  `GlueComponentRegistrationError`. Add the directories to the tag, or import
  the class in `components/__init__.py` to keep the short one. A component in a
  module directly inside `components/` is unaffected.

  A tag with a directory in it can be read two ways: `app/cards/fancy` is also
  the `components` module of `app/cards`. A tag that both readings resolve to
  different classes is refused as ambiguous.

### Features

- `{% glue_component %}` accepts a class's dotted path in place of a tag, such
  as `'app.components.cards.fancy.FancyComponent'`. It names one class, which
  may live outside any `components` module, and is not looked up in
  `DJANGO_GLUE_COMPONENTS`.

### Fixes

- A nested directory of a `components` package no longer needs an
  `__init__.py`. One without it was skipped silently.

- Disposing an object on the client also disposes every child whose address is
  derived from it. A child that arrived in a callable's response after its owner
  was only linked to that owner once it was read, so a child that was never read,
  such as the form of a model that was never rendered, stayed in the client's
  registry after its owner was disposed.

  Code that disposed a returned collection and kept using its items must now keep
  the collection for as long as it uses them: the items' addresses are derived
  from the collection's, so they are disposed with it.

## v1.2.1

### Fixes

- A formset accepts a new `ModelForm` row after that row makes a call of its
  own, such as loading a field's choices or validating. In v1.2.0 the call
  renewed the row's token with different `initial` values, so the formset's next
  `pop`, `validate` or `save` failed with "Submitted form token does not belong
  to this formset row." A form's token now signs the `initial` values the form
  was given, on every request.

## v1.2.0

### Breaking

- A component's re-render after page load keeps the stamped children still on
  the page instead of re-stamping them, so they keep their state and the
  response carries only the parent's markup (ADR 025). A page that re-renders or
  `$refresh()`es a parent so that its children redraw must now have each child
  declare `rerender_on` for the events that change it, or stamp it with the new
  `rerender_with_parent` flag. Otherwise those children show what they last
  rendered.
- `rerender_on` reaches every mounted component that lists the event, not only
  the source's ancestors, and one response's deliveries travel in one request.
  `Glue.listener` still hears only descendants.
- `DJANGO_GLUE_COMPONENTS_ROOT` is removed. Replace it with
  `DJANGO_GLUE_COMPONENTS = {'DIRS': [<root>]}`. A project that still sets it
  fails the system check `django_glue.E004`, whose hint gives the replacement
  (ADR 027).
- The component modules moved into the `django_glue.glue.components` package:
  `django_glue.glue.component` is now `django_glue.glue.components.component`,
  and `component_registry`, `component_discovery`, `component_naming`,
  `component_root` and `component_tag` are its `registry`, `discovery`,
  `naming`, `root` and `tag` modules. `Glue.Component` is unchanged, and
  `Component` and `component_registry` import from
  `django_glue.glue.components`.
- A formset's `save()` saves nothing when any row is invalid. It previously
  saved the valid rows. It also no longer calls each row's own `save`; it
  validates the rows and passes their Django forms to `save_forms` (ADR 028).
- `Component.get_view_kwargs()` is removed. Give a request-derived parameter a
  default and fill it in `__post_init__(request)`, and set `self.access` there.
  A class that still defines it raises `TypeError` when it is defined
  (ADR 030).
- `Component.get_context_data()` is removed, and a component's template context
  on a re-render is `component` alone. Read what the template shows from the
  component, as `{{ component.entries }}`, and add page context such as
  navigation to `self.context_data` in `__post_init__()`. A class that still
  defines it raises `TypeError` when it is defined (ADR 030).
- `layout_template` is renamed `view_template`, as a class attribute and as an
  `as_view()` argument. A class that still defines `layout_template` raises
  `TypeError` when it is defined (ADR 030).

### Features

- `@Glue.ComponentParameter` on a method declares a model parameter whose
  initializer turns the signed primary key into the row. A construction site may
  pass the loaded instance, which is used without a query; later requests resolve
  the key through the initializer. `DJANGO_GLUE_VERIFY_MODEL_PARAMETERS` (default
  `DEBUG`) checks supplied instances and emits
  `GlueModelParameterMismatchWarning` (ADR 021).
- A model parameter whose initializer takes the model as well as the key,
  `def host(self, model, pk)`, accepts a row of any concrete subclass of its
  return annotation, so one component can serve rows of several models. The
  token signs the model's label with the key (ADR 026).
- A model parameter whose initializer annotates its key as `| None`, such as
  `def entry(self, pk: int | None) -> TimeEntry`, may be left out for a record
  that does not exist yet. The initializer builds it on every request, and once
  a callable saves it the component is signed with the new key and edits that
  record. One component can therefore create a record or edit one (ADR 029).
- Component parameters are encoded through their annotation's adapter, so
  dataclass parameters are signed and restored (ADR 021).
- `__post_init__(self, request, **kwargs)` is the one hook that validates and
  sets up a component. It runs once when the component first appears on a
  page, after the user is authorized and before the first render (ADR 030):
    - Assigning `self.access` sets the level the component is signed with. A
      changed level is authorized again, and a component returned from a
      callable is capped at its caller's level.
    - Values added to `self.context_data` join the template context of the
      first render and of the view template. They are not kept, and a callable
      that changes `context_data` raises an error.
    - A URL capture, `as_view()` argument, or template-tag argument that is not
      a declared parameter is passed to the keyword of `__post_init__` with
      that name. It is not signed.
- A component's `rerender_on = (ChildComponent.event, ...)` re-renders it when
  a descendant emits one of those events, and `@Glue.listener(ChildComponent.event)`
  runs a method first. The client delivers the event through the component's
  built-in `$receive` call, and the child applies its own markup once the
  component's render has arrived, so the page changes once. A listener's `event.source` is the emitting
  component, rebuilt from its signed token (ADR 024).
- A component's signed identity records its ancestors: the component whose
  template stamped it, or whose callable returned it, and theirs.
- `DJANGO_GLUE_COMPONENTS` configures where component tags are looked up, shaped
  like Django's `TEMPLATES`: `DIRS` lists directories searched in order, and
  `APP_DIRS` (default `True`) also searches the installed apps by package path.
  A library's components resolve in any project that installs its apps, and a
  project overrides one by defining the same class at the same tag path under
  one of its `DIRS` (ADR 027).
- `Glue.formset()` and `Glue.FormSet` take `instances` (saved records to edit)
  and `initial` (prefilled blank rows), so a formset can load existing records.
  Removing a saved row with `pop` deletes its record on the next `save()`, and
  needs `Glue.Access.DELETE`. `save_forms` and `delete_removed` on a
  `Glue.FormSet` subclass replace how rows are saved and deleted (ADR 028).
- `new_row_defaults` on `Glue.formset()` and `Glue.FormSet` sets starting values
  on every new row, such as the key of the record the rows belong to. The values
  are signed and may name fields the form does not expose. The browser cannot
  change a default on a field the form does not expose or disables; a default on
  an editable field prefills it (ADR 028).
- A formset's `validate()` and `save()` load all submitted rows in one query,
  and `save()` writes only the saved rows that changed. Django's own validation
  queries for a form's foreign-key and unique fields still run per row
  (ADR 028).
- `Component.session` is a mutable mapping of server-side scratch state,
  scoped by the component class's module-qualified name and backed by the
  request's Django session. Setting or deleting a key marks the session
  modified, and Django saves it when the request completes, so a request that
  writes nothing saves nothing. The state is per-user, never signed, and
  never sent to the client. `DJANGO_GLUE_COMPONENT_SESSION_KEY_PREFIX`
  (default `django_glue:component_session:`) sets the prefix of the session
  keys it uses (ADR 031).
- `Glue.SessionAttr(default)`, a shortcut for `Glue.attr(default, session=True)`,
  declares a component value stored in the component's session. The client
  reads it and cannot write it, a callable changes it by assignment, and it
  survives a page load because the session, not the token, holds it. A
  callable that does not re-render its component, such as one declared with
  `skip_rerender=True`, still sends the session values it changed (ADR 031).

### Deprecated

- `Component.mount()` is deprecated and will be removed in a future version.
  Rename it to `__post_init__(self, request)`. An overridden `mount()` still
  runs, before `__post_init__`, and emits a `DeprecationWarning` (ADR 030).

### Changes

- A component constructed without a `name` is named after its class, as
  `as_view()` already named it, instead of the shared name `component`.
- A successful component callable re-renders its component in the same
  response. A callable returning a Glue object skips the render, and
  `@Glue.attr(skip_rerender=True)` opts any other callable out unless it changed
  one of the component's retained values (ADR 022). Callables that returned
  `self.render()` can return `None`, and a client `$refresh()` after the
  component's own action is no longer needed. Mark a callable that deletes the
  row its component shows with `skip_rerender=True`. The option is a
  `TypeError` at class definition anywhere but on a component.
- A component stamped by `{% glue_component %}` whose `is_authorized()` denies it
  renders nothing instead of failing the page. `as_view()` still responds 403.
- `GlueAuthorizationError` messages name the denied operation and attribute.

### Fixes

- A formset's `append(initial)` rejects any `initial` key that is not a field
  the form lets a user edit. It previously accepted every key, so a browser
  could set model fields the form did not expose on a new row, including the
  key of the record the row belongs to. A page that passed such a key declares
  `new_row_defaults` instead (ADR 028).
- A formset accepts a submitted row only if that formset issued it. It
  previously accepted a row issued by another formset with the same name, so a
  user could delete a record through a formset where they held
  `Glue.Access.DELETE` using a row from one where they held only `CHANGE`. A
  page loaded before the upgrade keeps working: its rows carry no issuer check
  until the page is loaded again (ADR 028).
- Describing a form's foreign-key or many-to-many field no longer loads the whole
  related table. The rows were read and then discarded, once per relation field
  for every form and every formset row. What the client receives is unchanged.
- A component nested inside another component, or inside any element with
  `x-data`, now sees its ancestors' Alpine data, as ordinary nested `x-data`
  does. Glue previously attached the `component` scope before Alpine had
  initialized the ancestors, so their `x-data` was missing from the nested
  component's scope.
- Re-rendering no longer stacks another `component` scope on a component root
  that Alpine had already initialized.

## v1.1.0

The full migration guide for these changes is at [Migration Guide](../migration.md).

### Breaking

- The state-model release removes the `metadata`/`state`/`manifest_list`
  envelopes, `TemplateGlue`, `Glue.template()`, `Glue.sequence()`, loading
  strategies, `load_state()`, and `related_field_config`.
- Attribute requests use a flat addressed `objects` envelope with editable
  `updates`; responses return authoritative addressed entries and independent
  per-address failures.
- Alpine.js and its morph plugin are bundled. Applications remove separate
  Alpine core and morph scripts and application calls to `Alpine.start()`.
- `Glue.view(url)` requests the real Django route. Install
  `GlueViewMiddleware` last in `MIDDLEWARE`; the redispatch endpoint is gone.
- `renderOuterHtml()` requires exactly one root element.

### Features

- Components mount through `{% glue_component %}` with typed Django
  parameters, stable keys, server HTML, Alpine morphing, and declared events.
- `Glue.ComponentParameter` declares a component construction parameter, a
  shorthand for `Glue.attr(parameter=True)`. Declaring one on a non-Component
  glue object is an error at class definition.
- `Component.as_view()` serves a component from a Django URL. By default the
  response is the component's HTML alone, for fetching with `Glue.view(url)`.
  With a layout template (the `layout_template` class attribute, or
  `as_view(layout_template=...)` to override it) the response is a full page,
  where a no-argument `{% glue_component %}` tag marks where the component
  renders.
- Mounted component `$refresh()` renders and morphs its root.
- `Glue.event(obj, name, payload)` fires a named event on a Glue object from an
  action without declaring it as a class attribute; `Glue.event()` with no
  arguments still returns the descriptor. It shares the declared-event
  validation and `effects.events` channel.
- Formsets retain signed row membership across requests and submit child form
  values together for validation and saving; `pop()` removes a row on the
  server.
- One live proxy exists per address. Disposed references become tombstones;
  reintroduction creates a new proxy generation.
- Model and form state is split into signed retained state, stable interface
  data, and derived output. `$refresh()` re-derives an object's output.
- Queryset rows and relation children have independent addresses. `ADD`
  permits creation without granting edits to persisted rows.
- `Glue.fields()` and nested `fields` paths configure relation projection;
  `choices=` supplies trusted relation choice sources.
- Queryset `filters=` and `ordering=` define signed client query permissions.
  Defaults follow exposed scalar and projected relation fields; explicit
  declarations can grant exact hidden paths, annotations, transforms, or reverse
  traversal. Full paths and lookups are validated on each request.
- Queryset seek keys are signed and bound to the queryset and the exact filter
  and ordering they continue. A forged, tampered, or replayed key is rejected,
  so an ordering-only permission cannot be used to filter.
- HTML responses register introduced objects before morphing. Matching keyed
  nodes preserve Alpine state, focus, and caret position.

- `Glue.Access.required_save_access` gives methods that both create and update
  the same target-derived access as `save()`: `ADD` for an unsaved instance,
  `CHANGE` for a persisted one. See the migration guide.

### Fixes

- A form on a `QuerySetGlue.new(initial)` draft now receives the admitted
  initial values before it is introduced, including raw foreign-key identities
  and many-to-many selections.
- A form on a `new()` draft can `validate()` at `ADD`; it previously required
  `CHANGE`, which a draft never has.
- Deleting or re-pointing a queryset row no longer disposes a projected
  relation object that other rows share. Only the object's owner disposes it.
- An expired projected relation object is reintroduced through its queryset.
  It previously failed with a server error.
- `loadMore()` continues querysets ordered by a related field path, such as
  `order_by=['-notification__sent_datetime']`.
- A form refresh no longer overwrites client-owned field members with server
  metadata, so choices narrowed with `overrideChoices()` survive it.

## v1.0.1

The entries below describe historical releases. Use the guides above for the
current API.

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
