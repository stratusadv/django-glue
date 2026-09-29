# Design documents

The `design/` directory holds the design documents for the Django Glue
redesign.

## Authority ladder

When documents disagree about intended behavior:

- `design/specs/core/state-model.md` governs state and transport.
- `design/specs/core/component-system.md` governs composition and
  rendering.
- `design/specs/core/overview.md` summarizes those two but does not
  override them.
- `design/roadmap.md` owns sequencing, gates, and deferred work — never
  protocol semantics. No runtime work is authorized merely
  because a design section exists; the roadmap gates determine readiness.
- `design/decisions/` records durable choices. A settled ADR
  is superseded by a later one, never silently rewritten.

`design/specs/README.md` is the entry point and reading order.

## Push back on design proposals

**When a requested design is worse than an alternative, say so before building
it.** The person proposing a design wants disagreement when it is warranted, not
a faithful implementation of every suggestion. Agreement is not the default.

Before drafting or extending a design:

- **Name the driving use case.** State the concrete problem the design solves. If
  it is not known, ask for it; a design without one is speculative surface.
- **Check existing mechanisms first.** Ask whether the spec already covers the
  case (a partial, a `@Glue.property` child, a `cached_property`, an existing
  Glue family, a deferred roadmap item). If it does, recommend that and explain
  what the new design would add over it.
- **Weigh the added surface.** A new concept, decorator, setting, or wire shape
  has to earn its place against the case it serves. A niche gain with a permanent
  cost is a reason to decline.
- **Notice when fixes chain.** If each revision patches a problem the previous
  one introduced, stop and step back rather than proposing the next patch. It
  usually means the design fights the model instead of fitting it.
- **Disagree plainly and early.** Give the recommendation, the reason, and the
  cheaper alternative in the first reply, not after several rounds of refinement.
  Then let the person decide; if they proceed, record the trade-off in the ADR.

**Known failure mode, confirmed to actually happen (2026-09-28):** an agent drafted
ADR 021 (component parameter initializers) to fix one per-row query problem in a
consumer's list, then revised it through a `queryset=` lambda, `is_authorized()`
scoping, a bound queryset hook, derived "parameters", and pickled-queryset
parameters, each round patching the last. Only when asked directly did it say
that the spec's existing answer, one owning component with rows as template
partials, solved the original problem with no Glue change, and that the new
mechanism mainly optimized the per-row-component pattern the spec discourages.
That assessment belonged in the first reply.

## Coordinated rewrite, not incremental rollout

The redesign is released only after the complete implementation and consumer
migration. Phases 2 through 5 are internal checkpoints on one diverging branch,
not deployable compatibility targets. Do not preserve a legacy API, wire shape,
or test expectation to make an intermediate phase safe to release.

## Tests

Use architectural tests only when they protect a durable design boundary through
meaningful behavior. Do not add historical tests whose sole purpose is asserting
that a legacy name or implementation detail no longer exists.
