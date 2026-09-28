# ADR 019: Ownership Follows Address Derivation; References Never Own

Status: Accepted; implemented on branch

Date: 2026-09-28

## Context

`state-model.md` §4 gives every addressed object exactly one owner. A
queryset owns its projected relation children, rows hold address references
to them, and "an address reference does not create a second owner, so the
ownership forest stays single-owner and acyclic". §10 derives a child's address
from its owner's address, path, family, and key. The server builds every
address that way (`address.child`, `address.item`, `address.transient`): a
row is `collection[pk]`, a relation child `collection.relation:pk`, and a
callable result `owner["t…"]`.

The client did not follow either rule:

- `childBinder._link()` set a child's `owner` to whichever record last resolved
  it. A row reading its `partner` took ownership of the partner that the
  collection owns and other rows share.
- `childBinder.refresh()` disposed every displaced child address, with no
  ownership check. When a row stopped listing its `partner` (a deleted row's
  successor policy has none), the shared partner was disposed.

In the portal, deleting one agreement from the list disposed the partner that
the other rows showed. Every row with that partner read `null` and raised
template errors until the list reloaded. The wrong owner also misrouted
recovery: reintroducing an expired shared child would have asked a row, which
holds only a reference, to rebuild it.

Once ownership was right, reintroduction reached the collection. That exposed
a server gap: `QuerySetGlue` sent relation-child paths to the row rebuild hook,
which filtered rows by `pk='relation.key'` and raised `ValueError`.

## Decision

**A record owns a child only when the child's address is derived from the
record's address.** That means the child's address starts with the record's
address followed by `.` or `[`. The client runtime applies the rule in two
places:

- Binding a child records its owner (and owner path) only for the owning
  record. A record that binds an address it did not derive holds a reference,
  and resolving it changes nothing.
- A displaced child is disposed only when its owner displaced it. A reference
  that goes away never disposes the object. The owner removing it, or the
  owner's own disposal, still does.

Addresses remain opaque to application code. The Glue runtime reads their
derivation because §10 defines ownership through it, and because the server is
the only source of addresses.

**Relation children follow the collection's slot rules on the server.** A live
relation child carries forward by address. A relation path named in
`reintroduce` is rebuilt through a row of the signed base queryset that still
references the related object, using the same construction and introduce
authorization as a batch. If no row references it, the child is dropped.
Reintroduce admission is unchanged, so only paths in the signed live children
map are accepted.

## Consequences

- Deleting or re-pointing one row no longer disposes a relation object that
  other rows share. The collection disposes it when its own membership stops
  referencing it.
- An expired shared relation child is reintroduced through its real owner, at
  its existing address.
- Client test fixtures that invented child addresses unrelated to their owner
  now use derived addresses, matching the server.
- Security: ownership is client lifecycle bookkeeping and grants no authority.
  Every request is still authorized from its own signed token. The rebuild path
  can only rebuild a relation child that the signed base queryset still
  reaches, under the collection's signed projection and current introduce
  authorization. A client can neither name an unissued path nor reach an
  unreferenced related object.
- Regression coverage:
  - `client_js/tests/disposal.test.js` ("address references do not create
    owners"): a reading row does not take ownership, a row dropping its
    reference leaves the child, and the owner dropping it disposes it.
  - `django_glue/tests/glue/test_collection_membership.py`
    (`QuerySetRelationChildMembershipTestCase`): carry-forward, reintroduction
    at the existing address with fresh data, drop when unreferenced, and
    admission failure for an unissued path.
  - The portal agreement list's delete test, where the surviving sibling row
    keeps its partner.
