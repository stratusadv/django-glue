# Recorded Concerns

Status: Living record; no action scheduled

This document holds concerns that were raised, understood, and deliberately not
acted on. It exists so that a settled decision is not re-litigated every time
someone new reads the design, and so that a concern with no owner today is still
findable if evidence later changes.

An entry here is not a defect and not a backlog item. Anything requiring work
belongs in [`roadmap.md`](roadmap.md); anything changing behaviour belongs in the
living design documents.

---

## Settled — not changing

### `Glue.attr` carries value roles, parameter exposure, and a callable form

`Glue.attr` declares reconstructors and editable state, may expose either as a
construction parameter, and also decorates client-callable methods. The design's
stated thesis is that a developer declares what a value *is* independently from
whether construction may supply it, and the callable form declares something
that is not a value at all. A split (`Glue.method(...)`, or reviving the rejected
`Glue.state()`) would give the vocabulary one idea per name, especially now that
`Glue.property`, `Glue.namespace`, `Glue.event`, `Glue.fields`, and `Glue.choices`
have expanded it anyway.

**Decision: keep `Glue.attr` as it is.** It is established, familiar to the team,
and present at every call site in both consuming projects. The cost of the
overload is documentation, not correctness — the declaration surface is now
tabulated in `state-model.md` §9 so the callable form is written down rather than
inferred from examples. Revisit only if the overload starts producing real
mistakes in review.

---

## Acknowledged — no action now

### Family shortcuts change meaning by omission

`Glue.queryset(request, name, target, ...)` registers a page root;
`Glue.queryset(target=..., fields=...)` returns an unbound object for use as a
child or a callable result. Same name, same signature, different lifecycle,
distinguished by which leading arguments were left out. Forgetting `request`
silently produces an unowned object whose failure surfaces later and elsewhere.

This sits oddly beside the design's rejection of implicit parameter-source
detection, which was refused because a typo should not change meaning. The
mitigations considered were a distinct constructor for the unbound form, or
requiring the registering form to be keyword-complete so the two cannot be
confused by argument count.

**No action now.** The dual-mode shortcut keeps one obvious name for each family
and the failure is loud enough in practice. Worth reconsidering if the unbound
form becomes the common case once child composition lands, since the balance of
which mode deserves the short name would then have changed.

---

## Open — pending discussion

### Collection-row policy size

**Deferred pending measurement**, not unresolved in principle.

`design.md` requires a queryset row to retain the authenticated scope that
introduced it. Read literally that puts a copy of the pickled continuation in
every row's policy, which extrapolates to roughly 130 KiB of signed tokens for a
fifty-row table. [`scoped-policy.md`](specs/proposals/scoped-policy.md) Rule 1 would fix it by
having a collection child reference its owner's policy instead of copying it —
one `owner` field, and the owner riding along as a passive entry in the existing
`objects` collection.

The estimate comes from the synthetic probe, not from a production-shaped
queryset. If a real continuation pickles to hundreds of bytes rather than the
probe's two KiB, fifty self-contained rows is tolerable and Rule 1 is not worth
its complexity. The roadmap's row-scale measurement constraint decides it.

Rows therefore keep self-contained policies for now, reconstructed through the
introducing queryset rather than the default manager.
