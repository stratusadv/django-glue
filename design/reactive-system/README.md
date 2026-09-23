# Reactive System Design

Status: Design complete; runtime implemented on `v1.1/base`, consumer migration pending

This directory is the internal source of truth for Django Glue's reactive
component and state-management redesign. It is intentionally separate from the
published MkDocs site.

## Reading order

1. [`design.md`](design.md) — system boundaries and invariants.
2. [`state-model.md`](state-model.md) — detailed value roles, security,
   transport, reconciliation, and adapter contracts.
3. [`component-system.md`](component-system.md) — composition, parameters,
   mounting, keys, rendering, and Alpine integration.
4. [`roadmap.md`](roadmap.md) — completed design gates, implementation phases,
   and deferred work.

Under evaluation:

- [`scoped-policy.md`](scoped-policy.md) — its Rule 2 (a projected relation is an
  addressed child) is **accepted** and now lives in `state-model.md` §4. Its
  Rule 1 (a collection child references its owner's policy rather than copying it)
  is **deferred** pending the roadmap's row-scale measurement. The document is
  retained for Rule 1's contract.

Supporting material:

- [`decisions/`](decisions/) records consequential decisions and their
  rationale. Accepted records are historical; a later change should supersede
  one rather than silently rewriting its outcome.
- [`concerns.md`](concerns.md) records concerns raised and deliberately not acted
  on, so a settled decision is not re-litigated. It is neither a backlog nor a
  defect list.
- [`research/`](research/) contains the code audit and framework comparison that
  support the design. These describe evidence, not the desired future state.

## Document authority

- The living design documents describe the current intended system and may be
  edited as the design develops.
- The roadmap describes sequencing and scope, never protocol semantics.
- ADRs explain why a durable choice was made. They do not replace the living
  specifications.
- When documents disagree about intended behavior, `state-model.md` governs
  state and transport while `component-system.md` governs composition and
  rendering. `design.md` summarizes those documents but does not override them.

No runtime implementation should begin merely because a design section exists.
The gates in `roadmap.md` determine readiness.
