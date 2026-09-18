# Reintegration

Date: 2026-09-18

This document covers one future merge from both ends: the state-model work that
was shelved, and the debt the component prototype is knowingly taking on. They
are the same merge viewed from opposite directions, which is why they share a
document — two documents would drift out of agreement.

## Where the state-model work stands

The reactive-system state-model refactor is shelved on **`v1.1/state-model`**
(commit `44803c0`, on top of the three commits previously on `v1.1/base`). Nothing
was discarded.

`STATE_MODEL_HANDOFF.md` on that branch is the detailed position and remains
accurate. In summary:

- **Roadmap phases 1–2 are complete.** Identity is locked in `_load_client_state`;
  value roles, the `editable=` projection, and `authorize()` are in place.
- **Phase 3 is substantially complete but not finished.** The
  `BaseGlueAttribute` hierarchy has been disconnected from the primary FormGlue,
  ModelGlue, and QuerySetGlue paths and replaced by attribute definitions, a
  registry, bound attributes, explicit field adapters, addressed children, and
  collection identity. The legacy modules still exist and are still exported —
  `attributes/base.py`, `state.py`, `readonly.py`, `composite.py`,
  `glue_object.py`, `callable.py`, and `attributes/django/` — and were verified
  unreachable at runtime but not yet deleted.
- **Phase 4 has not started.** Schema, `state_snapshot`, `unsigned_data`, and
  protocol admission do not exist.
- The focused suite was green at 225 tests when the branch was shelved.

The two test failures recorded in the handoff were fixed before shelving: a stale
`row['state']['red_corner']` traversal assertion, and a nested-relation-shape test
that asserted a protocol-admission behavior belonging to phase 4's boundary.

## Why it was set aside

The component system is the higher priority, and the two workstreams were
coupled in a way that made progress on components wait on wire work.

The state-model refactor is a coordinated rewrite with no compatibility envelope:
roadmap phases 2 through 5 are internal checkpoints that do not produce a
releasable library, and consumers migrate once at phase 6. That is a sound plan
for that work, but it means the wire is *in motion* for a long stretch — and the
component system as specified in `reactive-system/component-system.md` depends on
the end state of that motion: addresses, mount-only policies, `effects.events`,
`state_snapshot`, and the flat `objects` envelope.

Building components against a moving wire would have meant either blocking
components until phase 6, or rewriting the component layer at every phase gate.
Building them against the *current* wire decouples them entirely. The current wire
is stable, released, and — as the prototype spec documents — already supports
nested Glue objects, Glue objects in call results, and newly introduced objects in
responses. It is a more capable starting point than it appeared.

The cost is a known, bounded set of seams, listed below, plus one deliberate
double migration of the production dashboard.

## Plan to reintegrate

Reintegration happens **after** the component prototype reaches its gate (see
`components/spec.md` §Gate), not before.

1. **Finish phase 3 on `v1.1/state-model`.** Delete the legacy attribute
   hierarchy and its exports. This work is fully specified in
   `STATE_MODEL_HANDOFF.md` §"Finish removing the old attribute hierarchy" and was
   ready to execute when shelved.
2. **Merge `v1.1/base` into `v1.1/state-model`.** The component branch will have
   changed `v1.1/base` — most consequentially by removing `TemplateGlue`, whose
   removal the roadmap already wanted, and by switching HTML replacement to morph.
   Merge, never rebase.
3. **Implement phase 4** — schema, `state_snapshot`, `unsigned_data`, protocol
   admission — against the merged base.
4. **Close the seams below**, each of which becomes implementable as its
   prerequisite lands.
5. **Migrate the production dashboard once more**, this time to the end-state
   contract. See §"The deliberate double migration".

## The seams

Each is a place where the prototype knowingly does something the end-state design
replaces. Every one is recorded in `components/spec.md` at the point it is
introduced.

### 1. Declared children embed instead of being addressed

`components/spec.md` §6. A `Glue.property` returning a configured Glue object is
wrapped in `GlueObjectAttribute`; the child's state and metadata travel inside the
owner's manifest and it is named `f'{owner.name}.{attribute_name}'`.

`state-model.md` §7 replaces this with independent addressed islands. That naming
scheme is what produced the `entries.new` collision the design cites as motivating
evidence, so the collision class is inherited along with the mechanism.

**Closes when** addressed children land (phase 3 work already implemented on
`v1.1/state-model`: `address.py`, `children.py`, `GlueChildBinder`).

**Guard already in place:** the prototype does *not* embed a child's policy in the
owner's signed `identity`, because identity is signed per request and N children
would multiply the token by N. Only `state` and `metadata` embed.

### 2. Child properties are evaluated on every request

`components/spec.md` §6. `GlueAttributeCollector` calls `getattr` on every declared
attribute during collection, and collection happens on every request that touches
the object. A component's child property therefore runs even on interactions that
never address it.

`state-model.md` §10's slot-resolution table exists to prevent exactly this: *"a
child-producing `@Glue.property` is a factory for introduction, not a
derivation."*

This cannot be fixed on the current wire. Deciding not to evaluate a slot requires
knowing the live child set, which is the incoming token's `children` map — which
requires addressed children, which is seam 1.

**Mitigation:** child properties must return *configured* objects, not evaluated
ones. A `QuerySetGlue` holding an unevaluated queryset costs object construction,
not queries.

**Closes when** seam 1 closes and the slot-resolution table is implemented.

### 3. Lifecycle is a DOM-liveness sweep, not disposal

`components/spec.md` §10. Stamped components register flat with no owner edges, so
nothing removes one when its DOM disappears. The client instead sweeps the
registry after each morph, dropping entries whose `data-glue` root has left the
document.

This is a heuristic. It cannot dispose non-rendered objects, does not cascade, and
has no generation tracking — so it cannot prevent a late response from patching a
new incarnation at the same name, which `state-model.md` §7's generations exist
to do.

**Closes when** address ownership lands. The sweep must then be **deleted**, not
extended — a heuristic kept alongside real ownership becomes a second, conflicting
source of truth about liveness.

### 4. Callable results have no lifecycle

`components/spec.md` §11. A callable may return a configured Glue object and the
client registers a proxy for it, but without `component-system.md` §8's lifecycle:
no transient key beneath the caller's address, no capping of the result's
capability by the caller's effective capability, no owner-cascade disposal.

A returned object registers flat and is reclaimed by seam 3's sweep if it renders,
or leaks until page unload if it does not — which is the common case for a model
handed into a modal.

This is the most visible seam at runtime.

**Closes when** addresses and transient-key ownership land.

### 5. Names are hashed, not addressed

`components/spec.md` §7. A stamped component's name is derived from
`(parent_name, tag_name, canonical(key))` and hashed to a JavaScript-safe
identifier.

This is a flat address: the derivation matches `state-model.md`'s (owner,
canonical path, family, key) except that the owner segment is baked into a hash
rather than kept as a traversable path.

**Closes by replacement, not rework.** Reintegration swaps the hash for a real
address; the derivation inputs and the stability requirement are unchanged. This
is the cheapest seam to close and was designed that way on purpose.

### 6. Deferred features that were never approximated

Not seams so much as absences, recorded so nobody concludes they were forgotten:
slots, `$refresh()`, `$on()` and declared events, `authorize()`,
`Glue.attr(editable=True)`, and per-parameter serializers.

Each was deliberately left unimplemented rather than approximated, on the
principle that a weaker contract recorded under a specification's name is worse
than an absent one. Slots are the exception in sequencing: they are deferred for a
design reason (slot content's lifetime versus independent child re-render) rather
than a wire reason, and are the first work after the prototype gate.

## The deliberate double migration

The production time-entry dashboard in `stratusadv-portal` will be refactored
twice: once onto the component prototype as a final acceptance step after the
gate, and again onto the end-state contract at reintegration.

This is a chosen cost. The roadmap schedules consumer migration once, at phase 6,
specifically to avoid repeat work — but the prototype needs a real-world proof
that a `test_project` port cannot fully supply, and the portal pins
`django-glue==1.0.1` from PyPI, so the refactor will run against a source override
on a dedicated branch rather than against a release.

What makes this acceptable rather than wasteful: the first migration is a
prototype validation whose *purpose* is to find friction, and friction found there
is information the reintegration design wants. What would make it wasteful is
shipping it. The portal's component refactor stays on its own branch until the
end-state contract exists.

## Authority

While the component work is active:

- `components/spec.md` governs anything on `v1.1/components`.
- `reactive-system/` describes the deferred target. It is not binding on component
  work, and its `AGENTS.md` rules — no compatibility envelope, never preserve
  legacy code, coordinated rewrite — apply to `v1.1/state-model`, where they are
  correct.
- This document records what each side owes the other.
