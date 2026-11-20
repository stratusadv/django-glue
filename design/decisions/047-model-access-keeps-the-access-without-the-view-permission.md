# ADR 047: Model Access Keeps The Access Without The View Permission

Status: Accepted

Date: 2026-11-19

Partly supersedes [ADR 046](046-a-component-takes-its-access-from-model-permissions.md).

## Context

ADR 046 made `Glue.ModelAccessMixin` raise `PermissionDenied` in its
`__post_init__` when the user lacks the model's view permission. The same ADR
says the derived access is a default a subclass overrides by assigning
`self.access` after `super().__post_init__(request)`. The refusal breaks that:
it is raised inside `super()`, before the subclass's assignment runs, so a
subclass can change the level the mixin derives but not the refusal.

That matters to a project that does not authorize with Django's model
permissions. Profitly authorizes with company roles and grants no model
permissions, so every one of its users would be refused by a component that
mixes the mixin in, whatever the component then assigns.

## Decision

Without the model's view permission, the mixin leaves `self.access` as it
was: the level the component was constructed with, `VIEW` when none was given,
or what an earlier `__post_init__` in the chain assigned. It raises nothing.

The mixin does not define `get_permission_model()` itself. It is listed before
the component class so that its `__post_init__` wraps the component's, and a
method it defined would then hide the one a base component already supplies,
such as a library's list component that knows the model of its queryset. It
reads the method from the component, and names it when it is missing.

**The hook is renamed `get_permission_model()`**, from ADR 046's
`get_access_model()`. The old name differed from the helper
`get_model_access()` only in word order, though one returns a model and the
other an access level. The new name says what it returns and what for.

**A component names its model with either a `permission_model` class
attribute or the method.** The attribute is the plain case:
`permission_model = Role`. The method is needed when the model is known only
per instance: one delete confirmation class serves the row of any model it is
built with, a form component built from options takes its form class as a
parameter, and a list's model comes from its `get_queryset()`.

**The declaration nearest the component's own class wins.** The mixin looks
through the class's MRO and uses the first class that sets `permission_model`
or defines `get_permission_model()`. So a subclass overrides its base
whichever way each names the model: `permission_model = Role` on a list
overrides the model its base infers from the queryset, and a method on a
subclass overrides an attribute its base set. A plain "attribute first" or
"method first" rule would let a base's choice beat its subclass's.

Who may open a page stays the page's own guard, such as a
`permission_required` decorator on its URL or on `is_authorized()`, which
already answers a denial with a 403. A component returned from a callable is
still capped at its producer's access.

## Consequences

- A subclass's assignment after `super().__post_init__(request)` is always the
  level signed, with or without the view permission, as ADR 046 intended.
- A component that mixes the mixin in no longer refuses a user on its own; a
  page that must be closed to users without the view permission says so with
  its guard, as a page without the mixin does.

## Rejected Alternatives

- **A `permission_model` attribute that the mixin's own
  `get_permission_model()` returns by default**, as Django's `model` and
  `get_queryset()` work. The mixin is listed before the component class, so
  its method would hide the one a base component defines.
- **A generic parameter**, `ModelAccessMixin[Role]`. It is per class as an
  attribute is, and Python keeps it at runtime only in `__orig_bases__`,
  which a further subclass does not carry.

- **Keeping the refusal behind a class attribute** that a subclass turns off.
  It is a setting for one case, and a subclass that sets its own access would
  have to know to turn it off as well.
- **Refusing in `is_authorized()` instead.** It is asked again after
  `__post_init__`, but it cannot tell a level the subclass chose from the one
  the mixin left, so it would overrule the subclass in the same way.
