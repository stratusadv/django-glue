# ADR 033: A View Decorator Guards A Component Through `is_authorized()`

Status: Accepted; implemented on branch

Date: 2026-10-09

## Context

A component registered to a URL was guarded by wrapping `as_view()` in a view
decorator:

```python
path('dashboard/', permission_required('time_tracker.view_timeentry')(
    TimeEntryDashboardComponent.as_view()
), name='dashboard'),
```

Every one of the twelve component URLs in profitly, stratusadv-portal and
django-spire's test project was wrapped this way, always in `login_required` or
a `permission_required`. The wrapping is awkward to write, and it guards less
than it appears to. The decorator runs on the page load only. A later call goes
to Glue's own endpoint and rebuilds the component from its token, so the URL's
decorator never runs again, and a component stamped with `{% glue_component %}`
has no URL to decorate.

`is_authorized()` is the check that runs at all three points, so projects that
needed a real guard declared the rule twice: the portal's dashboard named
`time_tracker.view_timeentry` in its URL decorator and again in
`is_authorized()`.

The developers who write these components decorate function views daily and
rarely write class-based views. The guard had to keep that habit, and their
existing decorators, including django-spire's own `permission_required`.

A view decorator could already be placed on `is_authorized()` with Django's
`method_decorator`, but the result was unsafe. Glue tested the answer with
`if not self.is_authorized(...)`. `login_required` answers a denial by
returning a redirect, which is a truthy object, so a denial was read as an
authorization.

## Decision

**A view decorator on `is_authorized()`, applied with `method_decorator`, is the
supported way to guard a component.**

```python
class TimeEntryDashboardComponent(Glue.Component):
    @method_decorator(permission_required('time_tracker.view_timeentry'))
    def is_authorized(self, request, operation):
        return self.user_id in (None, request.user.pk)
```

Three rules make that safe and useful:

1. **Only `True` authorizes.** `False` denies. A response returned in place of a
   boolean denies, and the denial keeps the response. Any other value raises
   `TypeError` naming the class, so a rule that returns the wrong thing fails
   loudly instead of denying or allowing by accident.
2. **`PermissionDenied` raised from `is_authorized()` is a denial**, reported
   like any other, not an unhandled error.
3. **`as_view()` returns the response a denial carries.** A page load denied by
   `login_required` redirects to the login page. A denial with no response is
   the 403 it always was.

Every place Glue consults `is_authorized()` goes through one method,
`BaseGlue._authorize()`, which applies these rules. The rule belongs to every
Glue object, because `is_authorized()` does; only the component view uses the
response.

## Consequences

- One declaration guards the page load, a stamp and every later call, with the
  decorators a project already has. The URL pattern needs no wrapper.
- A decorator and an object-level rule combine: the decorator gates the
  request, and the method body decides what the decorator cannot express.
- Wrapping `as_view()` in the URL pattern still works and still guards only the
  page load.
- `is_authorized()` must return a real boolean. An override that returned
  another truthy or falsy value, such as a model instance or `None`, now raises
  `TypeError`. No override in profitly, stratusadv-portal or django-spire does.
- The decorator receives the request and the operation, not the URL's captured
  arguments. A decorator that reads one, such as `pk`, cannot be used here.
- A decorator that is not an access check has no meaning on `is_authorized()`.
  `require_safe` would deny every call, since calls are POST requests.
- A redirect is only used by the page load. A denied stamp still renders
  nothing, and a denied call still fails its entry with `not_authorized`.

## Rejected Alternatives

- **An `as_view_decorators` class attribute applied to the view.** It takes any
  view decorator and its name is honest about its reach, but it guards the page
  load only, which leaves the duplicated rule in place. It has no consumer once
  the access decorators move to `is_authorized()`: all twelve wrappers are
  access checks.
- **The same attribute, also checked on stamps and calls by running the
  decorators around a dummy view.** One attribute would then mean "view
  decorators for the URL" and "access rules for the component" at once.
  Decorators that are not access checks would misfire on Glue's requests, and
  `cache_page` could cache the dummy response under the page's own URL.
- **Glue's own `login_required`, `permission_required` and `user_passes_test`
  class decorators.** A clean mechanism, but a second set of decorators with
  Django's names that are not Django's, and django-spire's decorator would need
  rebuilding on top of them.
- **Access mixins modelled on `LoginRequiredMixin`.** The right shape for a
  team that writes class-based views. This one does not.
- **Making the request the first argument of `is_authorized()`**, so that a bare
  decorator works without `method_decorator`. The method would have to stop
  being an ordinary method and take the component as an explicit argument,
  which breaks every existing override on every Glue object.
- **Declaring the URL on the component class.** Considered alongside this.
  Collecting the routes needs every components module imported at startup,
  which reverses ADR 014's lazy lookup; one class can serve several URLs; and
  the URL's namespace lives in the URLconf tree, not on the class. With the
  wrapper gone, a component is registered exactly as a class-based view is.
