# ADR 016: Server Field Metadata Never Shadows a Field Class Member

Status: Accepted; implemented on branch

Date: 2026-09-28

## Context

A client field proxy (`client_js/src/proxies/fields/base.ts`) receives server
metadata such as label, required, widget, and choices whenever its form is
introduced or refreshed. The proxy applied it with
`Object.assign(this, metadata)`, excluding only `errors`, which an earlier fix
had special-cased.

Field classes also define members of their own that own client-side state,
with getters or setters that manage it. A relation field's `choices` setter is
one of them: it holds the choice list the application narrowed with
`overrideChoices()`. The server sends `choices: []` for a relation field, so any
response that refreshed the form assigned that empty list through the setter
and erased the override. In the portal's time-entry edit modal, the Project
dropdown went empty as soon as a dependent field refreshed the form.

Special-casing each colliding key (`errors`, then `choices`) would keep
reintroducing the bug whenever a field class added a member with the same name
as a metadata key.

## Decision

Server metadata is assigned only for keys the field's class does not define
anywhere on its prototype chain (`key in prototype`). Those keys land as plain
data properties and are replaced on every metadata update. Keys that a field
class defines are never written through or shadowed. The field class owns
that state, and server metadata cannot reset it.

## Consequences

- A refresh keeps `overrideChoices()`, validation errors, values, and any
  future client-owned member.
- A field class that wants server data for a member it defines must read it
  from the record explicitly. Metadata no longer reaches it implicitly.
- The `errors` special case is gone, because the general rule covers it.
- Regression coverage: `client_js/tests/fields_form_function.test.js`,
  "overridden relation choices survive a response that refreshes the field".
