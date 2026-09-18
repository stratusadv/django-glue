# ADR 009: Model Creation as an ADD Capability

Status: Accepted for the redesign; implementation pending

Date: 2026-09-16

## Context

The existing `VIEW < CHANGE < DELETE` access cascade cannot express a common
policy: a client may create an object but may not edit any persisted object.
Treating creation as `CHANGE` gives the client more authority than it needs.
Adding an `allow_create` flag would create a second permission system beside the
access cascade and would make every access check combine two independently
configured values.

Creation also matters for projected to-many relations. A configured queryset
should retain its `QuerySetGlue` surface when projected, including
`gorilla.skills.new()`, without making the existing related rows editable or
restoring the removed `related_field_config` API.

## Decision

Add `GlueAccess.ADD` and order the cascade:

```text
VIEW < ADD < CHANGE < DELETE
```

`ADD` includes read access and grants creation, but not mutation or deletion of
persisted objects. `CHANGE` and `DELETE` include creation through the ordinary
cascade. This is a Glue capability hierarchy, not a mirror of Django's
orthogonal model permissions; current application authorization remains an
independent required check.

`QuerySetGlue.new(initial)` requires `ADD`. Its `initial` mapping is admitted
only against the signed editable projection. A new draft receives only `ADD`
authority. After its first successful save, its successor becomes a persisted
row child with the introducing queryset's normal row access: `VIEW` for an
ADD-only queryset, `CHANGE` for a CHANGE queryset, and `DELETE` for a DELETE
queryset.

Persisted rows of an ADD-only queryset are always `VIEW`. Saving an unsaved
model or model form requires `ADD`; saving a persisted target requires `CHANGE`;
deleting one requires `DELETE`. The signed target identity, not a client value,
determines which check applies.

An explicitly projected to-many or reverse relation remains an addressed
`QuerySetGlue` child. When its introducing model or queryset has `ADD` or
stronger access, the relation child receives exactly `ADD`, never implicit
`CHANGE` or `DELETE`. Existing related rows therefore remain read-only while
`.new()` is available. The relation adapter signs its owner and relation
identity. `new(initial)` introduces an unsaved relation-owned draft; its first
successful `save()` performs creation and attachment atomically. Reverse foreign
keys inject the owner key server-side; many-to-many relations add the saved
object to the exact signed relation. Relations that require extra through-model
data do not expose generic `.new()` and require an explicitly declared callable.

## Consequences

- Create-only workflows use `access=Glue.Access.ADD`; no `allow_create` flag or
  revived `related_field_config` is introduced.
- `gorillas[0].skills.new()` is available when `skills` is explicitly projected
  and the introducing capability is at least `ADD`.
- ADD on a root queryset also exposes that root's `.new()`. Relation-only
  creation uses an existing typed child property returning
  `Glue.queryset(..., access=Glue.Access.ADD)` while the root remains `VIEW`.
- A newly saved object is attached to that exact relation before success is
  reported, and the same response reconciles authoritative membership, ordering,
  annotations, and counts. No extra refresh is required to observe attachment.
- Existing related objects never become editable merely because creation is
  enabled.
- Query filtering and ordering remain limited to the signed paths derived from
  the relation's projected fields; `ADD` grants no additional query traversal.
- An unsaved relation owner cannot create related objects because there is no
  stable owner identity to sign or attach.
- Application `authorize()` checks remain mandatory at introduction,
  reconstruction, and invocation. Possessing `ADD` does not imply a Django
  `add` permission or bypass row/tenant policy.

## Rejected alternatives

- Treat creation as `CHANGE`, which cannot represent create-only access.
- Add an `allow_create` boolean, which creates a second permission axis and
  ambiguous combinations with `GlueAccess`.
- Restore `related_field_config` or add a relation-only public configuration
  API.
- Return an unattached object from relation `.new()`, which violates the
  relation surface the call was made through.
