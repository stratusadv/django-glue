# ADR 046: A Component Takes Its Access From Model Permissions

Status: Accepted

Date: 2026-11-19

Builds on [ADR 030](030-component-post-init.md).

## Context

ADR 030 made `__post_init__` the place a component decides what the user may
do, by assigning `self.access`. In practice that decision is almost always the
same one: the user's Django permissions on one model, mapped onto `GlueAccess`.
Stratus Portal writes it by hand in about thirty places, and the copies
disagree. An agreement's detail page maps `delete_agreement` to `DELETE` and
`change_agreement` to `CHANGE`; its list and the deal list also give `CHANGE`
to a user who holds only `add_*`, which grants an update the user was never
given. Spire's model components, such as its scroll and form components, have
the same need and no shared answer.

`GlueAccess` already names Django's four default model permissions, `view`,
`add`, `change` and `delete`, and orders them so that each level grants the
ones below it. Django's permissions are not ordered: a user can hold
`delete_*` without `change_*`.

## Decision

`get_model_access(user, model)` returns the highest `GlueAccess` whose model
permission the user holds together with the permission of every level below
it, and `None` when the user does not hold the view permission:

| Permissions held | Access |
|---|---|
| none, or `delete` alone | `None` |
| `view` | `VIEW` |
| `view`, `add` | `ADD` |
| `view`, `change`, `delete` | `VIEW` |
| all four | `DELETE` |

`Glue.ModelAccessMixin` uses it. A component that mixes it in names its model
with `get_access_model()`, and the mixin's `__post_init__` assigns the access
`get_model_access()` returns, or raises `PermissionDenied` when it returns
`None`:

```python
class RoleListComponent(Glue.ModelAccessMixin, Glue.Component):
    def get_access_model(self):
        return Role
```

**The derived access is a default, not a rule.** A subclass that assigns
`self.access` after `super().__post_init__(request)` overrides it, and the
level it leaves is the one signed. A subclass that overrides
`get_access_model()` reads another model's permissions, such as a parent app's.

**Only the levels held in full count.** Each `GlueAccess` level grants every
level below it, so the access a permission grants is only safe when the user
holds the permissions below it as well. Taking the highest permission held
would give a user with `delete` but not `change` the `CHANGE` that `DELETE`
includes.

**The helper takes a user, not a request.** The user is all it reads, and a
caller outside a component, such as a view or a template tag, may have only a
user.

**A returned component keeps Glue's cap.** A component a callable returns is
capped at the access of the component that returned it, after its
`__post_init__` (ADR 030), so a mixin component never gets more access than
its producer has, whatever the user's permissions.

## Consequences

- A model component declares its model and gets its access, the portal's
  hand-written mappings can be replaced by one rule, and the add-grants-change
  workaround goes, since `ADD` is meaningful on its own (ADR 009, ADR 018).
- The access is decided when the component is introduced and signed, as any
  assigned access is. A permission revoked while a page is open takes effect
  when the token is next issued. A component that must check current
  permission on every call overrides `is_authorized()`, which Glue asks on
  every call.
- A user who holds `change_*` without `add_*` gets `VIEW`. A project that
  grants permissions that way assigns `self.access` itself.

## Rejected Alternatives

- **Checking the permissions again in `is_authorized()`** on every call. A
  later call runs on a component rebuilt from its token, which cannot tell a
  derived access from one a subclass assigned, so the check would overrule
  the subclass's choice.
- **A `get_access()` method to override.** Assigning `self.access` in
  `__post_init__` already overrides the default, and is how every other
  component sets its access. A second way to do the same thing would make
  each one look as though it might override the other.
- **Taking the highest permission held**, without the levels below it. See
  above.
- **Honoring an `access=` passed to the constructor.** A component's `access`
  defaults to `VIEW`, so a `VIEW` given on purpose cannot be told from none
  given. A component that must be read-only assigns `self.access` itself.
