# ADR 010: Target-derived required access via callable `required_access`

Status: Accepted; implemented on branch

Date: 2026-09-16

## Context

ADR 009 and `state-model.md` §3 establish that "the target identity, not a
client value, determines which check applies": saving an unsaved model or model
form requires `ADD`; saving a persisted target requires `CHANGE`. But a
declaration has only a static `required_access=...`, so one attribute cannot
express two different gates.

Two workarounds were tried and rejected:

- An in-body access re-check behind a static decorator. Marking `save` as
  `VIEW` (or `CHANGE`) to get past the declared gate and then enforcing the real
  `ADD`-versus-`CHANGE` branch inside the method duplicates the access check in
  a second location and misrepresents the declared contract — the client-facing
  capability says something weaker than what actually runs.
- A second, parallel permission value. ADR 009 already rejected a second axis;
  a per-target variant alongside `required_access` would recreate the ambiguity
  that `allow_create` caused.

The gate genuinely depends on the signed target. The declaration contract
should be able to say that plainly.

## Decision

`required_access` on a declaration accepts either a static `GlueAccess` or a
callable resolving to one at use time:

```python
GlueAccess | Callable[[BaseGlue], GlueAccess]
```

A callable receives the reconstructed glue object — its target already
re-derived from the signed policy identity — and returns the `GlueAccess` that
*that* target requires. It is resolved server-side, per request, at the same
enforcement points a static value already flows through:

- attribute-call resolution (`from_attribute_call_resolver_context`);
- the protocol access check ahead of attribute invocation;
- the `_require_authorization(GlueOperation(..., required_access=...))` call.

This is a declaration feature of the new attribute system
(`DeclaredAttributeOptions` → `GlueAttributeDefinition` → enforcement); the
legacy attribute hierarchy does not participate.

The built-in save targets illustrate the pattern:

- `ModelGlue.save` — `ADD` while `instance.pk is None`, `CHANGE` once persisted.
- `FormGlue.save` — `ADD` while the bound form's `instance` is absent or
  unsaved, `CHANGE` once persisted; a plain form is always create-only.
- `QuerySetGlue.new` stays a static `ADD` — a draft is always create-in-progress
  regardless of the reconstructing collection.

## Consequences

- The declaration reads as what it means; there is no in-body access re-check
  and no misleading static gate on `save`.
- A callable is code, not data: it is never serialized into the policy token or
  metadata, and only the *resolved* `GlueAccess` reaches the wire.
- Resolution is against signed reconstruction, so it cannot be steered by
  client input — it keeps the guarantee ADR 009 stated for save admission.
- Static values and callables are interchangeable at every enforcement point;
  existing declarations and their tests are unaffected.
- `_resolve_required_access` is the single resolution point on `BaseGlue`, so
  future per-target gates (deletion branch included) declare the same way.

## Rejected alternatives

- In-body access re-check behind a static gate — duplicated, misrepresenting
  enforcement, and easy to skip by editing only the method body.
- A second, parallel "per-target access" declaration option — a second
  permission axis, exactly what ADR 009 refused with `allow_create`.
- Widening the relevant `save` declarations to a broad static `CHANGE` and
  relying on `authorize()` to narrow creation — loses the `ADD` signal on the
  declaration surface and cannot be verified from the class alone.
