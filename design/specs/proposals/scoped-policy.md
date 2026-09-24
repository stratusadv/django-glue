# Collection Child Policy

Status: **Rules 2 and 3 accepted and moved into `state-model.md` §4. Rule 1
deferred pending the roadmap's row-scale measurement.** This document is
retained for Rule 1's contract and for the reasoning behind all three.

Date: 2026-09-16 (revised; supersedes the scoped-policy draft of 2026-09-14)

Relates to: [`state-model.md`](../core/state-model.md) §4, §8, §10 ·
[`decisions/004-addressed-object-composition.md`](../../decisions/004-addressed-object-composition.md) ·
[`decisions/009-add-access.md`](../../decisions/009-add-access.md) ·
[`concerns.md`](../../concerns.md)

---

## Revision note

The first draft of this document proposed a general **scoped policy**: a new
signed artifact shared by sibling addresses, bound to each instance by a digest.
It is retired here in favour of something considerably smaller.

Two findings collapsed it:

- The to-one relation half of the problem evaporated. Once that relation scope
  carries no continuation (below), independent relation tokens are already
  cheap, and scoping them saves on the order of a kilobyte. That does not
  justify a second token kind. A to-many relation is separately retained as a
  bounded queryset under Rule 3.
- The row half does not need a *new* shared artifact, because a shared artifact
  already exists: the queryset's own policy token. Binding to it is simpler than
  inventing a scope, and binding on its **stable address** rather than a digest
  removes the reissue-cascade problem the scoped draft had to manage.

What follows is the residue: one rule for rows, one for to-one relations, and
one for to-many relation collections.

## The problem

`design.md`'s walk of the recent-chats escape hatch requires that a
queryset-produced row's policy "retain the authenticated scope that introduced it
as well as its immutable PK," because reconstructing the row through the model's
unrestricted default manager would discard the queryset's authorization boundary.
That requirement is correct — today's `ModelGlue._reconstruct_from_policy` does
exactly the thing it forbids.

Read literally, though, it says every row carries its own copy of the pickled
continuation. Extrapolating the §Policy-token size probe — a 4.36 KiB token
carrying a two-KiB opaque query — a fifty-row table becomes roughly 130 KiB of
signed tokens before any state. The requirement is right and its literal reading
is unaffordable.

## Rule 1 — a collection child's policy references its owner's

A row's policy carries only what varies:

```json
{
  "owner": "dash#7f3a9c21.entries",
  "key": 471,
  "state_snapshot": { "description": "Rewrote the parser" }
}
```

Everything else — subject, model identity, continuation, read and editable
projections, capability — is read from the **owner's existing policy token**,
which the client already holds because the collection is a live addressed object
and its child's lifecycle owner.

### Where the owner token travels

Nowhere new. The owner is an ordinary entry in the existing `objects`
collection, present but passive — carrying its token and neither `updates` nor
`call`:

```json
{
  "objects": [
    { "address": "dash#7f3a9c21.entries",
      "policy_token": "<queryset>" },

    { "address": "dash#7f3a9c21.entries[471]",
      "policy_token": "<row>",
      "updates": { "description": "Rewrote the parser" },
      "call": { "attribute": "save", "kwargs": {} } }
  ]
}
```

This needs no second top-level key and no new artifact, and it deduplicates for
free: a batch editing five rows of one collection carries the owner entry **once**,
because an entry is keyed by address and the five rows name that address inside
their own signed tokens.

Four rules govern it:

- **Required presence.** An entry whose signed policy names an `owner` is
  rejected during protocol admission unless that owner address is present in the
  same `objects` collection. This is the request-side mirror of the staged-apply
  rule that a referenced child must be live or introduced in the same response.
- **Passive entries do not act.** An owner entry carrying `updates` or `call` is
  an ordinary participating entry as well; one carrying neither participates only
  as a reconstruction input.
- **Passive entries produce no response entry.** Nothing advanced on them, so the
  derived-omission rules leave them out of the response entirely. The client's
  held token remains current.
- **Owner failure fails its dependants.** If the owner token is expired or
  invalid, its entry carries the corresponding `error` and every entry naming it
  carries `owner_unavailable`. The remedy is reintroduction of the collection
  (§10), which reissues the owner and its live children together.

#### This does not weaken the independence invariant

`state-model.md` §10 says a batch "never embeds one policy token inside another,
supplies ancestor authority, or merges state snapshots," and `component-system.md`
§7 says a child "does not grant or reconstruct parent authority." Both remain
true and both are about the *upward* direction — a child manufacturing authority
for its parent — which stays forbidden.

An owner token travels downward and only ever **narrows**: it supplies the
queryset that bounds which row may be fetched, and the projection that bounds
which fields may be written. It cannot widen a child's capability, and a child
still cannot act on its owner without the owner being an actual participating
entry with its own call.

The independence invariant is therefore scoped to *participating* addresses: a
passive owner is part of a child's reconstruction inputs, not a batch peer.
Bundled and unbundled execution still produce identical results for every entry
that acts.

`state-model.md` §10's sentence needs amending to say this explicitly; as written
it forbids the mechanism.

### Verification order

1. Verify the **owner** token: signature, subject, session, expiry, namespace.
2. Verify the **row** token, and require its `owner` field to equal the owner
   token's signed address. A mismatch is a hard failure; this is what prevents
   pairing a row with a collection that did not produce it.
3. Decode the continuation from the owner token, through the allowlisting
   unpickler and encoded-size bound.
4. Reconstruct the base queryset and fetch the row **within it** —
   `base.get(pk=key)`, never the default manager. A key outside the collection is
   a 404, which is already `QuerySetGlue.get`'s behaviour and already right: a row
   can leave a bound filter between render and interaction.
5. Run `authorize()` for the row (§3). A collection-level check may short-circuit,
   but never replaces the per-row check.
6. Hydrate `state_snapshot`, admit `updates` against the owner's **editable**
   projection, invoke the callable.

### Why binding on the owner address, not a digest

The owner address is stable by §8 — derived from owner address, attribute path,
family and key, and explicitly unchanged by a server-authored parameter
transition. A digest over the owner's signed bytes is not: it changes on every
reissue, so binding to it would invalidate every row whenever the collection's
token advanced, and a response reissuing a collection would have to reissue all
its rows in the same envelope.

Binding on the address avoids that entirely. The collection's token may advance
its cursor, rebase its state, or roll its expiry, and live rows stay valid.

### Why key substitution is not a hole

The key sits inside the signed row token, so it cannot be altered. Acting on
another row requires that row's signed token, which the client holds only if the
server issued it — which means the row was inside the authorized collection.
Even granting an unsigned key, reaching row B through collection A grants exactly
what `queryset.get(pk=B)` already grants under A's own capability. The collection
*is* the boundary; moving within it is not escalation.

### Scope

This applies wherever a collection introduces same-family children under one
configuration: queryset rows, formset forms, and sequence items of one family. A
standalone `ModelGlue`, `FormGlue`, component, or page root is unaffected and
keeps its self-contained token.

## Rule 2 — a projected to-one relation is an addressed child with no continuation

> **Accepted.** This rule now lives in
> [`state-model.md`](../core/state-model.md#a-projected-relation-is-an-addressed-child),
> which is authoritative. The text below is the original argument for it.

`fields=Glue.fields('id', 'description', project=('id', 'name'))` introduces the
to-one relation `project` as an addressed `ModelGlue` child, not a flattened
leaf. Its policy is self-contained — model, key, projection, capability — and
carries **no continuation**.

A row's continuation is free and meaningful: the developer authored
`TimeEntry.objects.for_user(request.user)`, and that queryset *is* the permission
statement. A relation has no authored queryset. Its authorization statement is
"any project reachable from a row of this collection," and synthesizing a
continuation for it means Glue inventing a reverse subquery the developer never
wrote — expensive on large tables, and a reverse traversal the design denies by
default elsewhere.

The bound comes instead from two properties that already hold:

1. **Instances are signed and only the server issues them.** A client cannot
   fabricate a policy for an arbitrary project id, so it can only address
   projects the server actually projected from authorized rows. Enumeration is
   closed by issuance, not by a filter.
2. **`authorize()` runs per instance on every request** (§3). Reconstruction is
   `Project.objects.get(pk=key)`, and the application's rule — not the
   reconstruction path — decides whether this user may still read it.

This is a deliberate, reviewable difference from rows. The residual exposure is
the replay property the state model already accepts: a project policy issued
while the user had access stays usable until expiry even if the row that
introduced it leaves the collection. `authorize()` is the declared place to close
that. A project needing a hard bound declares the relation as an explicit child
property with its own configured queryset, which restores a real continuation.

To-one relation children default to `VIEW`. Editing requires an explicit
declaration, because a related object referenced by many rows is one shared
address and an edit through one row is visible in all of them — correct, but
surprising enough in a table that it should be opted into.

### Ownership and deduplication

Two rows referencing the same project resolve to **one** address and one proxy.
The **collection** owns relation children; rows hold address references, and §4
already establishes that an address reference does not create a second owner, so
the single-owner forest is preserved.

This is the reason a relation child beats a flattened leaf on cost as well as on
behaviour: a leaf duplicates the project's data on every row, while a child is
one entry referenced many times. Fifty entries across six projects is six
children, not fifty.

## Rule 3 — a projected to-many relation is an addressed queryset

> **Accepted.** This rule now lives in
> [`state-model.md`](../core/state-model.md#a-projected-relation-is-an-addressed-child),
> which is authoritative, and is refined by ADR 009.

A projected to-many or reverse relation is a `QuerySetGlue` child rather than a
plain collection. It preserves the normal queryset client surface while signing
the exact owner identity, relation identity, projected fields, and query
capability. Unlike Rule 2's to-one child, this child has a continuation: the
bound related manager is itself the server-selected collection scope, and every
client filter, ordering, count, and row lookup can only narrow it.

The relation queryset defaults to `VIEW`. When its introducing capability is
`ADD` or stronger, it receives exactly `ADD`; persisted related rows remain
`VIEW`, while `new(initial)` may introduce an unsaved ADD draft. Saving that
draft atomically creates and attaches it through the signed relation and then
reconciles the relation in the same response. `CHANGE` and `DELETE` never flow
implicitly to existing related rows.

This split preserves the security reason behind Rule 2. Glue still does not
invent a reverse scope for a singular object. A relation manager already is a
bounded collection operation, so retaining it for a to-many queryset is not an
unrestricted default-manager reconstruction.

## What this costs

| | Self-contained rows | This proposal |
| --- | --- | --- |
| 50 rows | ~130 KiB | ~10 KiB |
| plus a 6-project relation | ~170 KiB | ~12 KiB |

Extrapolated from the existing synthetic probe; the roadmap's row-scale
measurement constraint still governs the real numbers.

Signature *count* does not rise. Each row already receives a full signed policy
through `_build_child_model_payload`, so this makes each existing signature cover
a smaller payload rather than adding new ones.

The complexity added is deliberately narrow:

- A collection child's policy has an `owner` field and omits the shared material.
- A request acting on such a child includes its owner as a passive entry in the
  existing `objects` collection, and verification checks that the two agree.
- The client resolves a relation reference to a shared address rather than
  inlining per-row data.

No new token kind, no digest binding, no new top-level wire key, no reissue
cascade.
Every other rule in §8 and §10 is untouched: addresses stay opaque and stable,
entries stay independent, per-address `error` still scopes failure, and the staged
client apply is unchanged except that an owner token is verified before the
children that reference it.

## Open question

**Does this subsume transient callable-result children?** A callable returning
configured objects repeatedly could issue owner-referencing children rather than
self-contained ones, which would make `concerns.md`'s unbounded-`children` worry a
question of cheap references rather than eviction. Deliberately unanswered here;
`P1` is decided after this proposal is accepted or rejected.
