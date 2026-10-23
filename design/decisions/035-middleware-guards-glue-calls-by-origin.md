# ADR 035: Middleware Guards Each Glue Call By The Object's Origin

Status: Accepted

Date: 2026-10-22

## Context

A multi-tenant Django project names the tenant in the URL
(`/<uuid:company_uuid>/invoices/42/`) and guards it with middleware: a
`process_view` hook reads the tenant from the URL's arguments, checks the user's
membership fresh, and answers a non-member with a 404. Every page, form post,
JSON view and `Glue.view` fragment passes through that check, because each one
is a request to a URL under the tenant's prefix.

A Glue call does not. It goes to Glue's own endpoint,
`/__dg__/callable_attribute/`, whose URL names no tenant, so the middleware has
nothing to check. The object is rebuilt from its policy token, which proves the
session and the user but not that the user still belongs to the tenant whose
page issued it. A member removed from a company keeps acting on that company's
objects through the tokens in an open tab until they expire, 24 hours after
issue (ADR 013). `component-system.md` says as much: URL guards cover page
retrieval, and later calls use their own endpoint.

`is_authorized()` runs on every call, and the specification names tenant
membership as the kind of rule it holds, but it does not close the gap on its
own:

- `Glue.model()`, `Glue.form()`, `Glue.queryset()` and `Glue.formset()` objects
  are built by factories. A project cannot override their `is_authorized()`.
- A component has to carry its tenant as a parameter and repeat the check, and
  a component that forgets is not checked.
- Checks inside a call that depend on the request's tenant, such as a
  permission backend that answers per company, find no tenant on the request.

Two consumers need the gap closed. Profitly is building company tenancy for its
first release, and its components expose `Glue.model()` and `Glue.form()`
children. Showcase already runs as a multi-tenant application and works around
the gap with a replacement for Glue's endpoint: a view mounted at Glue's URL name
that decodes every token in the request, reads the company from the component's
signed parameters, resolves membership and the license agreement, answers any
refusal with one 404, and only then hands over to Glue. It refuses every object
that is not a component, because only components can carry the company, and it
depends on the token's internal layout.

Livewire solves the same problem with persistent middleware. When a component
renders, Livewire writes the page's path and method into the component's
checksummed snapshot. On every later update it matches that path against the
router again and runs the page route's authorization middleware, per component;
components added during an update inherit their parent's path. Calls still go
to one central endpoint.

## Decision

**A policy token signs the path that issued the object, and every Django
middleware that defines `process_glue_call(request, glue_call)` runs for each
object in a call, against that path.**

```python
class CompanyMiddleware(GlueMiddlewareMixin):
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        company_uuid = view_kwargs.pop('company_uuid', None)
        if company_uuid is not None and not company_context_resolve(request, company_uuid):
            raise Http404

    def process_glue_call(self, request, glue_call):
        company_uuid = glue_call.origin.kwargs.get('company_uuid')
        if company_uuid is not None and not company_context_resolve(request, company_uuid):
            raise Http404
```

One class guards both kinds of request with one rule: `process_view` reads the
tenant from the live URL, `process_glue_call` from the URL that issued the
object.

### The origin

1. **A policy signs `origin`, the `path_info` of the request that issued it.**
   A page or a `Glue.view` fragment issues its objects with its own path. An
   object introduced while a call is being resolved inherits the origin of the
   entry being resolved, never the call endpoint's path. The query string is not
   part of the origin.
2. **Glue resolves the origin with `resolve()` only when it runs hooks.** When
   at least one hook is installed, an origin that no longer resolves, because a
   deploy removed or renamed its route, refuses the entry: a hook that cannot
   read the origin must not be bypassed. A project without hooks never resolves
   an origin, so a renamed route costs it nothing. A token issued before this
   release has no origin and is refused as an invalid policy in every project.

### The hook

3. **Glue finds the hooks in `MIDDLEWARE`.** Every class listed there that
   defines `process_glue_call` takes part, in list order. `GlueMiddlewareMixin`
   documents the hook and gives type checkers its signature; a class that
   defines the method without the mixin is found too, as Django finds
   `process_view`. There is no separate setting.
4. **Glue builds its own instance of each class**, once, with a `get_response`
   that is never called. Django keeps its middleware instances inside the
   request handler, out of reach. `process_glue_call` therefore must not depend
   on state that Django's instance set up.
5. **The hook runs for every entry the call resolves**, including entries sent
   only to be refreshed and owners sent for reintroduction: after the token is
   verified and before the object is rebuilt, its `is_authorized()` runs, its
   updates are admitted or its attribute is invoked. It does not run when a
   page or a fragment introduces objects; Django's own middleware has already
   run for that request.
6. **`glue_call` is a read-only `GlueCall`** carrying `origin` (the resolved
   `ResolverMatch`), `address`, `namespace`, `kind` (`call`, `update` or
   `refresh`) and `attribute`. It is not a `GlueOperation`: the access an
   operation requires is declared on the object, which does not exist yet when
   the hook runs. It carries nothing else from the token: a hook decides from
   the origin, and a rule about one object belongs in that object's
   `is_authorized()`.
7. **Returning `None` continues. Raising `PermissionDenied`,
   `GlueAuthorizationError` or `Http404` denies that entry alone**, reported as
   `not_authorized` like any other refusal. The other entries in the call are
   resolved as usual. `Http404` is accepted so the function a project's
   `process_view` uses can be shared without wrapping.
8. **Hooks are synchronous**, like Glue's call view.

The order for one entry is: verify the token, run each `process_glue_call`,
rebuild the object, consult `is_authorized()`, admit updates, invoke. A hook can
deny but never grant; an object is authorized only when every hook and its own
`is_authorized()` allow it.

## Consequences

- A project guards pages and Glue calls with one middleware class and one
  membership function. A removed member is refused on their next call, not up to
  24 hours later.
- Every Glue family is covered, because every policy carries an origin. A
  project no longer needs a component parameter to carry the tenant, nor to
  refuse model, form and queryset objects.
- Context a hook sets on the request, such as `request.company`, is in place
  when the object is rebuilt and when its `is_authorized()` runs, so
  per-company permission checks and `method_decorator(owner_required)` work
  inside calls. A hook that sets context must set or clear it for every entry,
  so one entry's context does not reach the next.
- The call endpoint, its URL, the client and the wire shapes do not change.
  Glue's tests and projects' tests that post to `__dg__:callable_attribute` keep
  working.
- A policy grows by its origin path. Resolving an origin is one `resolve()` per
  entry; a hook that queries should memoize per request, never across requests,
  so a batch costs one membership query per tenant.
- Tokens issued before the release are refused once, and so are tokens whose
  route was removed by a deploy. The client already handles a refused entry.
- The origin is provenance, not authority. It never widens what a token may do,
  so a child still authorizes against its own address and token. A child that
  inherits its parent's origin is only ever narrowed by it.
- A hook denies one entry. A project that wants a refused call to answer with
  one response for the whole request, as Showcase's uniform 404 does, does that
  with ordinary Django middleware on the call route.
- Showcase can replace its endpoint with a `process_glue_call` on its company
  middleware that reads `company_slug` from the origin and checks membership and
  the license agreement. It can then drop its token decoding and allow
  non-component objects. Its migration is not part of this release.

## Rejected Alternatives

- **Routing calls through the tenant's URL**, by mounting Glue's call route
  inside the tenant's prefix so the project's middleware sees the tenant. Each
  page needs to know which mount to call: a project-supplied `call_url(request)`
  function, a URL template, or a search for the nearest mount by namespace,
  filling its arguments from the page. Middleware that pops the tenant from the
  view's arguments empties what the search reads. The client is untrusted, so a
  token also has to be bound to the URL or arguments it was issued for, or it
  can be replayed through the root mount or another tenant's mount. A
  `Glue.view` fragment from another mount needs its own URL, which brings back
  per-object URLs and batches split by URL. Tenancy for Laravel takes this route
  for Livewire with path-based tenants and calls it the complicated case.
- **A public API exposing a call's signed objects to middleware**, so a
  project's middleware reads the tenant from the token. It turns per-object
  authority back into one decision per request: a batch spanning two tenants,
  or a model row with no tenant parameter, has no single answer.
- **Revoking sessions when access changes**, by folding an access version into
  `get_session_auth_hash()` so every token dies with the session. It needs no
  Glue change, but it decides nothing about permissions, logs a user out of
  every tenant when one membership changes, and cannot express access that
  lapses without an event.
- **A project-wide authorizer in its own setting**, `DJANGO_GLUE_AUTHORIZER` or
  a list of `DJANGO_GLUE_AUTHORIZATION_CLASSES`. The same check, but a second
  registry beside `MIDDLEWARE`, and the tenant rule split across two classes.
- **Per-object middleware that wraps the object's resolution**, built as
  `Middleware(get_result)` and called around each entry. It could clear context
  after the entry and reshape its result, but it is a pipeline contract with no
  consumer yet. A `process_glue_result` hook can be added beside
  `process_glue_call` when one appears, as Django added
  `process_template_response`.
- **Running the hook when objects are introduced.** A page or fragment has
  already passed Django's middleware, and objects introduced during a call are
  covered by the entry that introduced them.
- **Replaying the origin route's middleware, as Livewire does.** Django attaches
  middleware to the project, not to a route, so there is no route middleware to
  replay, and running the whole chain against a fabricated request is fragile.
