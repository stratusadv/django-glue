# ADR 017: Queryset Seek Keys Are Signed Continuation Data

Status: Accepted; implemented on branch

Date: 2026-09-28

## Context

`QuerySetGlue` pages with keyset seeking (`GlueCollectionCursor`). A batch
returns a `seek_key` holding the last row's ordering values, and `loadMore()`
sends it back to continue the window. The key was plain base64 JSON, and the
server compared its values directly against the ordering fields.

`state-model.md` ("Authenticated queryset continuation") makes continuation
data authenticated and never client input, and the documentation described
`loadMore()` as following "the signed continuation". The seek key was neither.
A client could therefore edit it:

- It could not escape the base queryset, and Django parameterises its values,
  so it was neither an injection path nor a row-scope bypass.
- It was a comparison oracle. A forged position asks for "rows whose ordering
  field is greater than X". ADR 015 lets `ordering=` grant sorting on a hidden
  field or annotation without granting filtering on it. A forged seek key turned
  that grant into `gt`/`lt` filtering, enough to binary-search the hidden
  value.
- The key was not bound to the queryset or query that issued it, so it could be
  replayed across queries.

A second defect showed up when Spire's scroll moved to continuation paging
(Spire ADR 0001). Encoding the next key read each ordering value with
`getattr(row, path)`. A related ordering path that the query capability
permits, such as `notification__sent_datetime`, raised `AttributeError`, so
`loadMore()` failed on any queryset ordered through a relation.

## Decision

**Seek keys are signed.** `QuerySetGlue` signs every key it issues, from a batch
or from a refreshed window, with a salt that binds the key to the queryset's
address and the exact filter and ordering it continues. A continuation request
must present a key that verifies under that salt. A key that is unsigned,
tampered with, issued by another queryset, or presented with different filters
or ordering fails with `GlueQuerySetCursorValidationError`. The cursor itself
still produces and consumes the raw position. Signing belongs to the queryset,
which owns the address and the query the key is bound to.

Signing provides integrity, not confidentiality, as it does for the policy
token. The ordering values of the last delivered row stay readable in the key,
but the client already holds that row.

**Ordering values follow relation paths.** The cursor reads an ordering value by
walking a `relation__field` path through to-one relations. A missing related
object reads as `None`, which the seek filter already places in the trailing
NULL bucket.

## Consequences

- Continuations match the spec and the documentation. An ordering-only grant
  stays ordering-only.
- A seek key is valid only for the queryset address and query that issued it.
  Changing the filter or ordering restarts from the first batch, which is what
  clients already do.
- Continuation paging works for every ordering the capability permits,
  including related paths.
- Regression coverage: `django_glue/tests/glue/test_queryset_pagination.py`
  rejects unsigned and forged positions, keys replayed under a different query
  or from another queryset, and continues a refreshed window's key. It also
  pages a relation-ordered queryset, including a nullable relation.
