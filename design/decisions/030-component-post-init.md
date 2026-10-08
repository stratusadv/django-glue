# ADR 030: `__post_init__` Is The One Place A Component Is Set Up

Status: Accepted; implemented on branch

Date: 2026-10-06

Supersedes [ADR 023](023-component-as-page.md).

## Context

An application developer has code that should run once, when a component first
appears on a page: check how it was configured, load something, choose what the
user may do, give the page a title. Before this decision that code had four
homes, chosen by lifecycle rules the developer had to know:

- **`get_view_kwargs(request, **url_kwargs)`**, a classmethod that ran before
  construction for URL views only, returned constructor arguments as an
  untyped dict, and was the only hook that could supply a required parameter
  or the access level. [ADR 023](023-component-as-page.md) deprecated it.
- **A Django view calling `component.as_page(request)`**, ADR 023's
  replacement: the application constructs the component itself.
- **`mount()`**, called at introduction with the request bound. It could not
  set access, because introduction authorized before calling it.
- **`get_context_data()`**, called on every render, where page context such as
  navigation was mixed with the data the component's own template shows.

None of these is wrong on its own terms, and ADR 023 explains why `mount()`
could not absorb `get_view_kwargs`. The cost is in the sum. A developer does
not think in terms of construction, introduction, and reconstruction. They
think the component starts once, at page load, and they want one safe place to
put code for that moment. `mount` did not read as that place, and three of the
four hooks existed only for cases it could not reach.

## Decision

`Component.__post_init__(self, request, **kwargs)` is the one hook an
application overrides to validate and set up a component. Glue calls it once
per introduction, after the constructor has assigned parameters and after the
component is authorized for the request and bound to it, and before the first
policy token and the first render. The name is the one dataclasses and
pydantic use for "the object is built, now finish it".

1. **It receives the request.** `self.request` is also bound; the argument is
   the same object.
2. **It receives init-only values.** A value passed to the constructor under a
   name that is not a declared parameter is held until introduction and passed
   to the keyword of `__post_init__` with that name. URL captures, `as_view()`
   arguments, template-tag arguments, and direct construction supply them
   alike. They are not signed and do not exist after the hook returns. A name
   that is neither a declared parameter nor a keyword of the class's hook
   still fails construction as an unknown parameter, and a hook that takes
   `**kwargs` accepts any name. A tag hashes the init-only values it stamps
   into the child's address, so they must be JSON-serializable there
   ([ADR 025](025-parent-renders-keep-mounted-children.md)).
3. **It may set access.** The component is authorized first at the level it was
   constructed with, `VIEW` when none was given. If the hook assigns a
   different `self.access`, Glue caps it at the access of the component whose
   callable returned this one, then authorizes the `introduce` operation again
   at the new level. The hook therefore always runs for a user who passed a
   check, and no level is signed that was not authorized.
4. **It may add page context.** `self.context_data` is a dict that joins the
   template context of the first render: the component's own first render and
   the view template around a URL view. It is not signed and not kept. A
   component rebuilt for a later action has it empty, and a callable or
   listener that changes it fails with an error naming the callable.
5. **The component is the context of its own template.** `get_context_data()`
   is removed. What a component's template shows on every render is read from
   the component: its attributes, `@Glue.property` values, and cached
   properties.
6. **`as_view()` is the only way a component serves a URL.** `as_page()` and
   `get_view_kwargs()` are removed. Request-derived parameters are declared
   with a default and filled in the hook.
7. **`layout_template` is renamed `view_template`**, as a class attribute and
   as an `as_view()` argument: it is the template of the view the component
   serves.
8. **`mount()` is deprecated.** An overridden `mount()` still runs, before
   `__post_init__`, and warns.

A class that still defines `get_view_kwargs`, `get_context_data`, or
`layout_template` raises `TypeError` when it is defined. Each would otherwise be
ignored without a sign: an access level dropped to `VIEW`, template variables
rendered blank, a page served as a fragment.

## Consequences

- An application has one hook to learn. Validation, initial state,
  request-derived parameters, access, and page context are all assignments
  inside `__post_init__`.
- `__post_init__` does not run when a component is rebuilt from its token for
  an action or refresh, which is the difference from the dataclass method it
  is named after. A plain attribute it sets is gone on the next request, and
  so are `context_data` and the init-only values. Anything a later action
  reads must be a declared attribute or be derived on demand. The
  `context_data` guard catches one form of this mistake; the others fail on
  the first action.
- A component whose hook raises its access is authorized twice at
  introduction. A component whose hook leaves access alone is authorized once,
  as before.
- A parameter that depends on the request can no longer be required: it needs a
  default for construction to succeed before the hook fills it.
- A page whose data the template read from `get_context_data()` must move that
  data onto the component. Query results become cached properties, read as
  `component.<name>`.
- The view layer no longer constructs components, so a request-derived page has
  no Django view to hang decorators on. `as_view()` returns an ordinary view
  that decorators wrap in the URL configuration.
- 1.1 applications break at import, with an error naming the replacement, if
  they define `get_view_kwargs`, `get_context_data`, or `layout_template`.

## Alternatives considered

- **Keep `mount()` and document it better.** It already ran at the right
  moment. Rejected because the name was the obstacle: developers did not
  recognise it as the place for setup, and it could not set access or receive
  values that are not parameters.
- **Call the hook from the constructor, as dataclasses do.** A component is
  constructed before it is introduced to a request and again on every
  reconstruction, so the hook would have no request, would run before
  authorization, and would run on every action.
- **Run the hook before authorization, so one check covers the final access.**
  Simpler, but the hook would run for users who are then refused. Authorizing
  first and again on a change keeps the hook a place where the user is known to
  be allowed in.
- **A separate `get_access(request)` hook.** It would decide the level before
  the first check. Setting `self.access` in `__post_init__` covers every case
  it would, and can also lower an explicitly passed level from data the hook
  loaded.
- **Require access to be set when none is passed.** It would make every
  display-only component state `VIEW`. `VIEW` remains the default.
- **Sign `context_data` into the token so it survives re-renders.** Its values
  would have to be serializable and would be visible to the client and carried
  on every response. Navigation context and query results are neither small nor
  serializable.
- **Keep `layout_template` as a deprecated alias.** 1.2.0 already breaks
  component APIs; one rename with a definition-time error is clearer than two
  names for a release.
