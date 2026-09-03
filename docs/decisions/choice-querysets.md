# Choice Sources and Related-Model Search

Status: Accepted

Date: 2026-09-02

## Context

Django Glue needs one concise interface for field choices, including richer
presentation data and server-side search for large related-model collections.
The API should not imply that every choice source is a queryset, and the browser
must not control ORM paths or serialization policy.

The initial design batched foreign-key choices with a seek cursor. That defended
an undesirable application shape: a conventional select should contain a small,
finite set, while a large relation is a search problem rather than an infinitely
paginated select.

## Decision

Applications configure choices through the source-polymorphic helper
`Glue.choices()`:

```python
status_choices = Glue.choices(Order.Status.choices)

company_choices = Glue.choices(
    Company.objects.filter(is_active=True),
    search_fields=['name', 'account_number'],
    fields=['name', 'account_number', 'logo_url'],
    search_limit=25,
)
```

Static choices pass through unchanged and retain Django's normal behavior.
Queryset sources are cloned and may carry immutable `QuerySetChoiceOptions` on
their Django `Query`, allowing configuration to survive queryset cloning and
`ModelChoiceField` assignment without requiring a custom queryset subclass.

A queryset with no `search_fields` is treated as a deliberately small choice set
and is loaded completely. A queryset with `search_fields` is a search-only source:
its unfiltered result is empty, and each non-empty query returns at most
`search_limit` matches. Search results preserve explicit queryset ordering;
otherwise Glue adds primary-key ordering for deterministic limits.

There is no relation-choice cursor, next-batch operation, or default batch size.
`QuerySetGlue` collection pagination remains a separate feature.

## Rich Choice Shape

Every related-model choice contains `value`, `label`, and an `obj` with `pk` and
`__str__`. Applications may add flat fields with `fields`. Those fields must be
concrete, non-relational, JSON-serializable model fields or annotations declared
on the queryset. Duplicate fields are removed while preserving declaration order.
Binary fields, relations, missing attributes, `pk`, and `__str__` are rejected.

`ModelChoiceField.to_field_name` and model `ForeignKey.to_field` determine the
submitted `value`; `obj.pk` remains the canonical model primary key.

## Search Semantics and Trust Boundary

Search fields and result limits are server-owned configuration. The browser sends
only the relation field name and search text. Search fields must be direct,
non-relational model fields or declared scalar annotations. Relationship traversal
is rejected. Glue combines multiple fields with `OR` and `icontains`.

Glue does not automatically call `distinct()`. It may be expensive, can interfere
with PostgreSQL `DISTINCT ON`, and does not reliably remove duplicates when
annotations or ordering columns differ. Applications needing related search data
must expose a scalar annotation and own its join and deduplication semantics.

## Browser Behavior and Cache Identity

The relation proxy shares default loaded choices when compatible fields have the
same server-provided cache key. Search results temporarily replace the visible
list but do not pollute that cache. A monotonically increasing search generation
prevents stale or cleared requests from overwriting newer state.

When a user selects search results, the proxy retains those choices independently
of the current result list so their rich labels remain available after search
clears. The server seeds every initial selection for searchable
`ModelChoiceField` and `ModelMultipleChoiceField` fields. Multi-select results are
returned in submitted-value order, and removing a value removes it from
`selectedChoices` without requiring another request.

The cache key includes an opaque fingerprint of the Django query, effective
options, and submitted value field. This fingerprint only tells browser proxies
whether they may share hydrated choices. It grants no query authority and is not
accepted from the browser.

## Queryset Policy

Registered model relations may carry a configured queryset in signed policy.
The serialized Django `Query` is a pickle and is decoded only after signature
verification. Same-version policy round trips are tested across all supported
Django versions; Django does not guarantee cross-version pickle compatibility.

## Consequences

- The public name remains flexible enough for future non-queryset choice sources.
- Small selects remain simple and complete; large datasets require intentional
  search UX.
- Applications own the performance of unsearchable querysets and should keep them
  bounded by domain design or filtering.
- Search result size, ORM access, and rich-object shape cannot be widened by a
  client request.
- Query cloning and signed-policy reconstruction remain compatibility-sensitive
  and require version-matrix coverage.

## Rejected Alternatives

- Foreign-key choice batching encourages large select controls and creates cursor,
  ordering, duplicate, and partial-selection semantics without improving the UX.
- `Glue.choice_queryset()` over-specifies the source type and prevents a coherent
  API for enums, static iterables, and future providers.
- Form-level dictionaries separate choice behavior from its source.
- Custom form fields or queryset subclasses conflict with normal Django APIs and
  application-defined classes.
- Client-submitted search fields, limits, or object fields cross the trust boundary.
- Automatically applying `distinct()` changes application query semantics.
