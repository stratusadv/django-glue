# ADR 045: A Component Knows When A Component View Serves It

Status: Accepted

Date: 2026-11-18

Refines [ADR 030](030-component-post-init.md).

## Context

ADR 030 made `__post_init__` the one place a component is set up, including the
page's context: `self.context_data` joins the first render and the view
template around a component that `as_view()` serves.

`__post_init__` runs the same way however the component is introduced: by
`as_view()`, by `{% glue_component %}`, or as a callable's result. So context
that only the page needs, such as its title and breadcrumbs, reaches every
embedding of the component too. Profitly's Sales Tax page shows the workaround
this forces: `RegistrationListPageComponent` is a subclass of the registration
list that exists only to add the page's navigation in `__post_init__`, so the
list embedded elsewhere does not get it. The other workaround, a keyword passed
at the URL such as `as_view(as_page=True)`, fails silently: forget it, and the
page loses its title.

## Decision

`Component.served_as_view` is a read-only property that is `True` when
`as_view()` is serving the component on this request, and `False` otherwise.
`as_view()` marks the component it builds before introducing it, so
`__post_init__` can read it:

```python
def __post_init__(self, request):
    super().__post_init__(request)

    if self.served_as_view:
        self.context_data.update(build_page_navigation(request))
```

Nothing is passed at the URL, and `as_view()`'s signature does not change.

It is a fact the component reads, not another hook. ADR 030 folded four hooks
into one because the developer thinks of one moment, the component's first
appearance, and wants one place for its code. A separate page-only hook would
split that moment again by a rule the developer has to learn. A fact keeps the
code in `__post_init__` and the branch visible where it is used.

**The name.** `served_as_view` ties the flag to the `as_view()` a developer sees
in `urls.py`, and says what happened on this request. `is_view` read as though
the component were a view. `is_page` would bring back the "component as page"
vocabulary ADR 030 retired with ADR 023. `registered_as_view` and `is_routed`
describe the class's URL binding, which is fixed once at import, while the flag
answers for this request: a class routed at one URL and embedded with the tag on
another page reads `False` on that page. "Registered" also already means the
component registry in Glue.

**After a token rebuild it is `False`.** It is not signed or kept in the policy
token. A component rebuilt from its token for a later call was not served by
`as_view()` on that request, and that request renders only the component's own
template, never the view template. `__post_init__` does not run on a rebuild
(ADR 030) and `context_data` is gone by then, so the flag has the same lifetime
as the context it exists to guard.

**A fragment response is a component view.** `as_view()` without a view
template still serves the component, so the flag is `True`. Whether a page
template wraps it is a separate fact, the component's `view_template`.

## Consequences

- A component adds page-only context under `if self.served_as_view:` in
  `__post_init__`, and the page subclass and the URL keyword are not needed.
- The flag belongs in `__post_init__`. A component template that branched on it
  would render differently on its first re-render, when the rebuilt component
  reads `False`; the components guide says so.
- One private attribute set by the constructor and by `as_view()`. Each way a
  component is introduced has a test: a view with and without a view template,
  the tag, a callable's result, and a rebuild from the token.

## Rejected Alternatives

- **A page-only hook**, such as `__post_view_init__`. It splits the first
  appearance into two hooks again, which ADR 030 undid.
- **A keyword at the URL**, `as_view(as_page=True)`. It works only when every
  URL remembers it, and forgetting it fails silently.
- **Signing the flag** so a rebuilt component reports where it was first
  served. Nothing a later call does depends on it: page context exists only for
  the first render.
