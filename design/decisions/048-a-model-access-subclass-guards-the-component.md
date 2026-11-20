# ADR 048: A Model Access Subclass Guards The Component

Status: Accepted

Date: 2026-11-20

Builds on [ADR 046](046-a-component-takes-its-access-from-model-permissions.md)
and [ADR 047](047-model-access-keeps-the-access-without-the-view-permission.md).

## Context

ADR 047 left who may open a component to the page's own guard. In practice
that guard is the same rule as the access the mixin derives: the user's
permissions on the component's model, compared with the level the component
needs. Stratus Portal's role list and role form each wrote it by hand in
`is_authorized()`, the form choosing `add_role` or `change_role` by whether it
creates or edits a row. A guard on the URL instead, such as
`permission_required`, protects only the page: a component a list opens in a
modal through a callable never passes through that URL.

ADR 047 rejected refusing in `ModelAccessMixin.is_authorized()`: the guard
reads permissions, not `self.access`, so it would turn away a user a subclass
had granted more, and that subclass would have to know to override the guard
as well. That holds for a component that grants access its own way, and is
why the guard is not added to `ModelAccessMixin` itself.

## Decision

**`Glue.ModelAccessRequiredMixin` subclasses `ModelAccessMixin` and adds the
guard.** It sets the access as `ModelAccessMixin` does, from the same
`permission_model` or `get_permission_model()`, and its `is_authorized()`
admits a user whose `get_model_access()` reaches `get_required_access()`.
Glue asks `is_authorized()` when the component first appears and on every
later call, so one rule guards the page, a component a callable returns, and
each action.

**`get_required_access()` is the level a component needs, `VIEW` when the
component defines none.** A component that needs more says so: a form
component returns `ADD` while it creates a row and `CHANGE` while it edits
one. The mixin knows nothing of forms, and does not define the method itself:
as with `get_permission_model()` (ADR 047), it is listed before the component
class, so a default of its own would hide a base component's.

**A refused page load redirects to log in, as Django's `permission_required`
decorator does.** `is_authorized()` answers with `redirect_to_login()`, which
`as_view()` returns in place of a 403 (ADR 033). `raise_exception = True`
answers `False` instead, a 403. A refused call is a 403 either way, since a
call's response is Glue's own.

`ModelAccessMixin` is unchanged and still never refuses. A component that
grants access its own way, such as to the owner of a row, mixes that in, or
overrides `is_authorized()` alongside the access it assigns.

## Consequences

- A component whose access is the user's model permissions guards itself
  with one base class, and its URL needs no decorator.
- The guard and the access read one model, named once.
- Each check reads the user's permissions, which Django caches on the user
  object, so the cost does not grow with the calls a request makes.

## Rejected Alternatives

- **The guard in `ModelAccessMixin` itself.** Rejected by ADR 047, for the
  reason above.
- **A separate guard mixin beside `ModelAccessMixin`.** A component that wants
  the guard always wants the derived access too, so it would list two mixins
  that must name the same model; the subclass shares the model lookup.
- **Answering a refused page load with a 403 by default.** The applications
  that use the mixin guard their pages with `permission_required`, which
  redirects; the default keeps their behaviour, and `raise_exception` is the
  same switch Django's own decorator and mixin offer.
