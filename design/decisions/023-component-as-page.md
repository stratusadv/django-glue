# ADR 023: Serve a Constructed Component with `as_page()`; Deprecate `get_view_kwargs`

Status: Superseded by [ADR 030](030-component-post-init.md)

Date: 2026-09-29

## Context

`component-system.md` §5 lets a component serve a URL through
`Component.as_view()`. Named URL captures and `as_view()` keyword arguments
become constructor parameters. When a parameter or the access ceiling depends
on the request, the component overrides a classmethod hook:

```python
@classmethod
def get_view_kwargs(cls, request, **url_kwargs) -> dict[str, Any]:
    ...
    return {
        **super().get_view_kwargs(request, **url_kwargs),
        'user_id': request.user.pk,
        'week_of': week_of,
        'access': access,
    }
```

`as_view()` pops `access` from the returned dict and passes the rest to the
constructor. Every application that needs a request-derived value overrides
this hook: the portal's time-entry dashboard, and Profitly's dashboard,
transaction review, month close and invoice builder.

The hook is hard to use correctly:

- **The contract is an untyped dict.** Nothing at the definition site says
  which keys are valid. The constructor's parameters are the real contract, and
  the hook restates them as string keys, one of which (`access`) is not a
  parameter at all. A misspelled key reaches the constructor's unknown-parameter
  error only when a request arrives.
- **It hides ordinary view logic inside the component.** Parsing a query
  string, choosing an access ceiling from Django permissions and falling back
  on a bad date are what a Django view does. Placed in a classmethod on the
  component, they read as component behaviour and invite the question why this
  is not `mount()`.
- **It is the wrong seam for `mount()`, but looks like it.** `mount()` runs
  after construction, so it cannot supply required parameters: construction
  fails first. It could not set `access` either, because introduction checks
  `is_authorized()` against it before `mount()` runs. And a `mount()` that
  derived parameters from the request would overwrite the values a parent
  stamped or an action passed. The hook exists only so `as_view()`, which has
  no parent, can build the constructor arguments that a parent would otherwise
  pass.

The hook stands in for a Django view function, and the application can write
that view directly if Glue lets it respond with a component it constructed
itself.

## Decision

Add an instance method that responds to a request with an already constructed
component:

```python
def as_page(self, request: HttpRequest, *, layout_template: str | None = None) -> HttpResponse
```

- It introduces the component into the request's Glue context, mounting it, and
  renders the layout template (the argument, else the class's
  `layout_template`) with the component in its context and marked for the
  no-argument `{% glue_component %}` tag. Without a layout template, it responds
  with the component's fragment, as `as_view()` does.
- An `is_authorized()` denial at introduction raises `PermissionDenied`, so
  Django responds 403, as `as_view()` does.
- A component constructed without an explicit `name` receives the same root
  name `as_view()` derives from its class, so both paths produce the same
  addresses.
- It does not restrict the HTTP method. The application's view decides which
  methods it serves, as any Django view does.

A request-derived page is then an ordinary view that constructs the component:

```python
@permission_required('time_tracker.view_timeentry', raise_exception=True)
def dashboard_view(request: HttpRequest) -> HttpResponse:
    requested = request.GET.get('date')
    ...
    component = TimeEntryDashboardComponent(user_id=request.user.pk, week_of=week_of, access=access)
    return component.as_page(request)
```

The parameters are the constructor's keyword arguments, so the component's
generated signature documents them to editors, and `access` is the constructor
argument it already is.

`as_view()` stays for the case it fits: URL captures and fixed keyword
arguments map straight onto parameters. It is reimplemented as
`cls(**parameters).as_page(request, layout_template=...)` under `require_safe`,
so the two paths share one introduction and rendering path.

`get_view_kwargs` shipped in v1.1.0, so v1.2.0 deprecates it rather than
removing it. `as_view()` still calls it, and a subclass that overrides it emits
a `DeprecationWarning` at class creation, which names `as_page()` as the
replacement. It will be removed in a future version. The five known overrides
migrate to view functions.

## Consequences

- Request-dependent pages are written as plain Django views, with decorators,
  query parsing and permission logic where Django developers expect them.
- The component's constructor becomes its only construction contract. A
  misspelled parameter is visible in the editor and fails on the first request
  to that view, the same as before, rather than after an untyped dict round-trip.
- `as_view()` narrows to the static-mapping case, which is how
  `component-system.md` §5 introduces it.
- A page that previously registered as `Component.as_view()` in `urls.py`
  registers a view function instead. The URL name and template are unchanged.
- `component-system.md` §5, the components guide and the changelog are updated
  to describe `as_page()`, the reimplemented `as_view()`, and the deprecation.

## Alternatives considered

- **Derive parameters in `mount()`.** Rejected for the timing reasons above:
  parameters are needed to construct the component and sign its identity, access
  is checked before `mount()`, and a request-derived `mount()` would override
  parent-supplied values.
- **A `from_request(cls, request, **url_kwargs) -> Self` classmethod.** Replaces
  the dict with a constructor call, which fixes the typing problem, but keeps
  view logic in a special hook on the component. `as_page()` removes the hook
  instead.
- **Keep `get_view_kwargs` and document its keys.** Leaves the untyped contract
  and the component-owned view logic in place.
- **A module function, `glue_page(request, component)`.** Equivalent behaviour.
  A method on the component matches `as_view()` and `render()`, and needs no
  extra import.
