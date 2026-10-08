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

### Form instances are not component parameters

A parent could want to hand a child a form it built, with initial values or with
errors from a failed submission. A parameter is fixed once stamped, while a form's
input, errors, and draft values change with every interaction and are already
signed and admitted by `FormGlue`. As a parameter the form would either freeze or
become a second copy of state `FormGlue` owns, and building a form saves the
parent no query.

**Decision: a component builds its form as a `@Glue.property` child from its
parameters** (the row as a model parameter, per ADR 021, plus any scalar initial
values). The parent passes what the form is built from, never the form.

---

## Acknowledged — no action now

### Querysets as component parameters

Considered with ADR 021. A queryset parameter could be signed as its pickled query,
reusing `QuerySetGlue`'s signing, restricted unpickler, and
`DJANGO_GLUE_MAX_QUERY_ENCODED_BYTES`: the token grows with the query rather than
the rows, every request re-runs it so results stay current, and its selections,
annotations, and filters travel with it. Signing the rows' primary keys instead
was rejected outright, because the token would grow with the rows and the list
would freeze to the rows that existed when the child was stamped.

It was not adopted because no current component needs it. Server-side lists are
built in a `cached_property` from scalar parameters, and a list the client pages or
filters is a `QuerySetGlue` child. The costs are a signed query in every
instance's token and markup, which suits one widget per page but not one per row,
and a parent saves a query only by passing the exact queryset it evaluated, not a
filtered slice of it.

**Reopen when** a reusable component must be handed an arbitrary query by its
parent, such as a generic table or picker, which scalar parameters cannot describe.

### Form classes as component parameters

A generic modal could take which form to render as a parameter signed by its dotted
path and restricted to subclasses of an allowed base, as `FormGlue` already signs
its form class. Today one `FormComponent` subclass per form covers the case in a
few lines, so the gain does not yet justify a new signed type and its import
restriction.

**Reopen when** the number of single-purpose form component subclasses becomes a
maintenance cost in a consuming project.

### Seeding derived values at construction

Considered with ADR 021: a value derived from a component's own parameters, such
as the entries a `TimeEntryDayComponent` lists, could be supplied by a parent that
already computed it, so the portal's week dashboard would issue one entry query
instead of eight. It was not adopted because such a value is not a parameter:
nothing about it is signed, and accepting it at construction would add a second
way into a component beside its parameters. The per-day cost is fixed at seven
children, not proportional to rows.

**Reopen when** a component tree pays a derived query per child at a scale that
grows with data, and restructuring it as one component with partials is not an
option.

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

### Glue-wide live re-scoping of signed keys

`ModelGlue` rebuilds its row with `model_class.objects.all()` and the signed key,
so a row that leaves a user's scope stays actionable until its token expires. ADR
021's model parameters re-apply scope on every interaction through their
initializer. Whether `ModelGlue` and queryset rows should also re-apply a
request-dependent scope is a separate, Glue-wide decision.
