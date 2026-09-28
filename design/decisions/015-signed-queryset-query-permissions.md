# ADR 015: Queryset Query Permissions Are Signed Full Paths and Lookups

Status: Accepted; implemented on branch

Date: 2026-09-28

## Context

A `QuerySetGlue` lets the client narrow and order its rows. `state-model.md`
states the bound ("the reconstructed base queryset still bounds every client
query and the signed query capability still governs all client-added filtering
and ordering"), but did not say what the capability contains or where its
defaults come from.

The pre-1.1 implementation validated only the first segment of a filter key and
did not validate `order_by` at all
([`research/comparative-analysis.md`](../research/comparative-analysis.md)). With a
relation exposed, a client could filter or sort on fields deliberately left out
of `fields=`, both on the bound model and on related models:
`skills__gorillas__rank_points__gte`, `order_by=['-rank_points']`. That is the
relation-traversal oracle behind `user__password__startswith` attacks. It let a
client extract hidden values one comparison at a time.

Glue 1.1 also closes relations by default (`state-model.md` §4): a related
object is visible only through an explicitly projected leaf. Query permissions
must follow the same boundary, or a query could reach data the projection
withholds.

## Decision

The query capability is signed into the queryset's policy as two
permission sets. The server enforces them on every request and revalidates them
against current model metadata when it reconstructs the queryset.

- **Filters** map a complete field path to the lookups allowed on it. A
  request's filter key is split into path and lookup, and both must be
  permitted exactly. A permitted path does not permit its prefixes, suffixes, or
  siblings.
- **Ordering** is a set of complete field paths. A request's `order_by` entry
  must name one of them, with an optional `-`.

**Defaults derive from exposure.** When `filters=` or `ordering=` is omitted,
the permitted paths are the exposed concrete scalar fields and the explicitly
projected related leaves. A relation's raw identifier (`project_id`, and
`project` naming the same column) is included without exposing any other field
of the related model. Default lookups are conservative per field type:

- `exact`, `in`, and `isnull` for every field;
- string containment and prefix/suffix lookups for character and text fields;
- range comparisons for numeric, date, time, and duration fields.

Default ordering excludes binary and JSON fields.

**Explicit declarations replace defaults.** `filters=` and `ordering=` replace
the derived set for that operation instead of extending it. `None` derives from
exposure, and an empty mapping or list disables the operation. An explicit
declaration may name a hidden field, an annotation, a registered transform, a
reverse or many-to-many traversal, or a non-default registered lookup. Each
path and lookup is validated against the model when the capability is created.
An explicit grant is a data-exposure decision: query access reveals
information about values even when the row values themselves stay hidden.

## Consequences

- The traversal oracle is closed by default. Reaching a hidden or related field
  through a query needs an explicit, reviewable declaration at the call site.
- Consumers that filtered or sorted on unexposed paths must declare them. The
  portal and Spire 1.1 migrations needed none: their searches and sorts
  used exposed fields.
- The capability travels in the signed policy, so client queries cannot widen
  it, and reconstruction rejects a capability that no longer matches the model.
- The continuation that pages a query must not reopen what the capability
  closes. ADR 017 signs seek keys so an ordering-only grant does not become a
  comparison filter.
