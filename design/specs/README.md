# Design Specifications

Status: Design complete; runtime implemented on `v1.1/base`, consumer migration pending

This directory holds Django Glue's governing specifications and proposed
extensions. It is separate from the published MkDocs site. Read the core
contract before a proposal; a proposal does not change the current contract
until accepted and folded into the core specs.

## Reading order

1. [`core/overview.md`](core/overview.md) — system boundaries and invariants.
2. [`core/state-model.md`](core/state-model.md) — detailed value roles, security,
   transport, reconciliation, and adapter contracts.
3. [`core/component-system.md`](core/component-system.md) — composition, parameters,
   mounting, keys, rendering, and Alpine integration.
4. [`../roadmap.md`](../roadmap.md) — completed design gates, implementation phases,
   and deferred work.

Under evaluation:

- [`proposals/scoped-policy.md`](proposals/scoped-policy.md) — its Rule 2 (a projected relation is an
  addressed child) is **accepted** and now lives in `core/state-model.md` §4. Its
  Rule 1 (a collection child references its owner's policy rather than copying it)
  is **deferred** pending the roadmap's row-scale measurement. The document is
  retained for Rule 1's contract.

Supporting material:

- [`../decisions/`](../decisions/) records consequential decisions and their
  rationale. Accepted records are historical; a later change should supersede
  one rather than silently rewriting its outcome.
- [`../concerns.md`](../concerns.md) records concerns raised and deliberately not acted
  on, so a settled decision is not re-litigated. It is neither a backlog nor a
  defect list.
- [`../research/`](../research/) contains the code audit and framework comparison that
  support the design. These describe evidence, not the desired future state.

## Document authority

- The living design documents describe the current intended system and may be
  edited as the design develops.
- The roadmap describes sequencing and scope, never protocol semantics.
- ADRs explain why a durable choice was made. They do not replace the living
  specifications.
- When documents disagree about intended behavior, `core/state-model.md`
  governs state and transport while `core/component-system.md` governs
  composition and rendering. `core/overview.md` summarizes those documents but
  does not override them.

No runtime implementation should begin merely because a design section exists.
The gates in [`../roadmap.md`](../roadmap.md) determine readiness.
