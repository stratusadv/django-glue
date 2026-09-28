# ADR 018: One Public Rule for the Access a Save Requires

Status: Accepted; implemented on branch

Date: 2026-09-28

## Context

ADR 009 gives a draft from `QuerySetGlue.new()` exactly `ADD` access, and says
the signed target decides what a save needs: `ADD` for an unsaved model or model
form, `CHANGE` for a persisted one. ADR 010 made that expressible by letting
`required_access` be a callable resolved against the reconstructed target.
`ModelGlue.save` and `FormGlue.save` each did so through their own private
function.

Two callers kept a fixed `CHANGE`:

- **`FormGlue.validate`.** Its `CHANGE` requirement predates `ADD`. A draft's
  form could be saved at `ADD` but could not be validated, so the form widgets'
  validation call failed before the user could submit.
- **Application save methods.** Consuming projects declare one form method,
  typically `save_model_obj`, that both creates and updates, with
  `@Glue.attr(required_access=Glue.Access.CHANGE)`. Under Glue 1.0 a `new()`
  draft inherited the queryset's `CHANGE` and passed. Under ADR 009 it has
  `ADD`, so every "Add" modal built on `queryset.new().form` was rejected. In
  the portal that covered seven flows: agreements, agreement client contacts
  and company reps, deals, solutions, and project time entries.

A fixed `ADD` is not a fix: through the cascade it would let an `ADD`-only
object call the method on a persisted instance and modify it, which ADR 009
exists to prevent. Glue's own tests created drafts only through its built-in
`save`, which already followed the target, so they did not catch either
caller.

## Decision

`GlueAccess.required_save_access(glue)`, published as
`Glue.Access.required_save_access`, is the single rule for the access a save of
a Glue object's target requires. It returns `ADD` while the target model
instance is unsaved, including a form with no instance, and `CHANGE` once it is
persisted. It reads a model object's `instance`, or a form object's
`form.instance`.

- `ModelGlue.save`, `FormGlue.save`, and `FormGlue.validate` declare it. The
  per-family private rules are removed. Validating an unsaved target is part of
  creating it and mutates nothing, so it needs no more access than saving it.
- Application methods that create and update through one entry point declare
  `@Glue.attr(required_access=Glue.Access.required_save_access)`. Methods that
  only ever edit persisted instances keep `Glue.Access.CHANGE`.

It is a static method on `GlueAccess` so that it sits beside the levels it
returns and is reachable through the existing `Glue.Access` export. Enum methods
are not members, so the access cascade is unchanged.

## Consequences

- "Add" modals built on `new()` drafts validate and save at `ADD`. A
  create-only object still cannot validate or save a persisted instance.
- The rule exists once, so a future change to what counts as unsaved (for
  example a draft identity other than `pk is None`) happens in one place.
- Consuming projects update the save methods their draft-based flows reach. The
  v1.1 migration guide documents the change.
- Regression coverage: `django_glue/tests/glue/test_add_creation.py`
  (`GlueSaveRequiredAccessTestCase`). An unsaved form validates at `ADD`, and a
  persisted one is denied. A `required_save_access` application method creates
  at `ADD`, is denied on a persisted target at `ADD`, and updates at `CHANGE`.
  A `CHANGE` queryset's `new()` draft form validates and saves through the
  application method.
