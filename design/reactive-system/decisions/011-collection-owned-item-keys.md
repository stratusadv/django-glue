# ADR 011: Collections Own Their Item Keys

Status: Accepted for the redesign; implementation pending

Date: 2026-09-17

## Context

State-model §8 gives every collection identity and addresses its items by a
stable key: each item's address is `collection_address + "[" + key + "]"`, the
collection records `{key: address}` in its signed `children` map, and on a later
request it re-derives and verifies each child address from the key that is
signed in the child's token. The key is therefore a property of the collection's
membership scheme, not of the item itself: a queryset key is the row PK, a
formset key is the form's membership key, a sequence key is the item key.

The first S1b seam draft put a `key` attribute on `BaseGlue`, stamped by the
owner and read by the child binder, so that each item carried its own
membership key. That attribute is used only when a `BaseGlue` is a child, and
its value is always already known to the collection that introduces the item.
It therefore hoists a collection-level concern onto the base class and
duplicates a value the introducing collection can always supply.

The address does encode the key as its final segment, but the wire treats the
canonical address as opaque and never reparses the display spelling
(state-model §8). The spec's reconstruction direction is key → address: the key
is signed in the child's token and the collection re-derives the address from
it, not the reverse.

## Decision

A collection owns its item-key derivation end to end; `BaseGlue` carries no
`key` attribute.

- **Build.** When introducing its live children, a collection yields `(key,
  child)` pairs — the key first, the item second. The key is the item's
  stable slot in that collection (row PK, form membership key, or item key).
  The child binder uses the key to form the item address as
  `collection_address + "[" + key + "]"` and signs that key into the item's token.
  The item `BaseGlue` is never asked for its own key.
- **Reconstruct.** On a later request the collection reads the item's key
  from the item's signed token (state-model §8) and re-derives and verifies
  the item address from it. An item whose key is unchanged keeps its address
  and proxy.

Each collection subclass supplies its own key scheme: `QuerySetGlue` yields
`str(row.pk)`, `FormSetGlue` and `SequenceGlue` yield their declared
membership keys. The binder stays uniform over `(key, child)` pairs, with no
family special-casing and no base-class field.

## Consequences

- `BaseGlue` stays clean; membership identity lives on the collection that
  knows the key scheme.
- The key remains a first-class signed field of the item token (state-model
  §8), so authority and reconstruction are unchanged.
- Adding a new collection family means implementing its key yield and key read,
  not touching `BaseGlue`.
- The child binder's input is `(key, child)` rather than a bare child, which
  keeps addressing uniform across queryset, formset, and sequence items.

## Rejected alternatives

- A `BaseGlue.key` attribute stamped by the owner; a child-only field hoisted
  onto the base class, duplicating a value the introducing collection already
  holds.
- Parsing the key out of the item's address spelling on reconstruct; the wire
  treats the address as opaque and the spec's direction is key → address, so
  the key is read from the signed token instead.

The complete contract remains in
[`../state-model.md`](../state-model.md#8-collections-get-identity-and-keys).
