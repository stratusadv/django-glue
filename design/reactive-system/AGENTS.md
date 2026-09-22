# Reactive-system rules (deferred workstream)

**Scope: this directory and the `v1.1/state-model` branch only.**

These rules were previously at `design/AGENTS.md` and applied repository-wide.
They now apply to the reactive-system redesign alone. They are correct for that
work and wrong for the component work, which is deliberately built on the current
wire — see [`../components/spec.md`](../components/spec.md) and
[`../REINTEGRATION.md`](../REINTEGRATION.md).

If you are working on components, stop reading here and read
[`../AGENTS.md`](../AGENTS.md) instead.

## The rule

**The design documents in this directory are the specification for the
reactive-system redesign. Follow them at all times. Never preserve legacy code
where it contradicts the spec — when the spec and the code disagree, the spec
wins. Write new code against the spec, not against the current runtime.**

Do not do either of these:

- **Do not preserve legacy behavior.** If the spec describes something
  differently than the current runtime does it, the current runtime is wrong and
  being migrated away from. Do not "keep it working" or shape a new contract to
  match it. Compatibility with the legacy shapes is explicitly out of scope
  (`roadmap.md`: "There is no compatibility envelope").
- **Do not reuse a legacy mechanism as a stand-in for a spec contract.** A new
  field or interface must mean what the spec says it means. If the only existing
  implementation is one-way or legacy-shaped, leave that contract unimplemented
  rather than record the legacy shape under the spec's name. Missing > wrong.

## Authority ladder

When documents disagree about intended behavior:

- [`state-model.md`](state-model.md) governs state and transport.
- [`component-system.md`](component-system.md) governs composition and rendering
  **on the redesigned wire**. It does not govern the component prototype; see
  [`../components/spec.md`](../components/spec.md).
- [`design.md`](design.md) summarizes those two but does not override them.
- [`roadmap.md`](roadmap.md) owns sequencing, gates, and deferred work — never
  protocol semantics. No runtime work is authorized merely because a design
  section exists; the roadmap gates determine readiness.
- [`decisions/`](decisions/) records durable choices. A settled ADR is superseded
  by a later one, never silently rewritten.

[`README.md`](README.md) is the entry point and reading order.

## What this means in practice

1. New code is written against the spec first. When in doubt, re-read the
   governing section of `state-model.md` / `component-system.md` before writing.
2. Anything in the repo that contradicts the spec is legacy to be replaced, not
   precedent to follow. Call it out, and change the code.
3. If you believe the spec is wrong or ambiguous, flag it rather than deciding in
   favor of the existing code. Do not widen or narrow the spec silently.
4. Tests verify the spec, not the legacy implementation. A test that encodes
   legacy behavior in contradiction with the spec should be updated, not defended.

## Coordinated rewrite, not incremental rollout

The redesign is released only after the complete implementation and consumer
migration. Phases 2 through 5 are internal checkpoints on one diverging branch,
not deployable compatibility targets. Do not preserve a legacy API, wire shape, or
test expectation to make an intermediate phase safe to release.

Prefer implementing the end-state contract and migrating its consumers and tests.
A narrow legacy edit is acceptable when it is the simplest way to prove a new
contract incrementally, but it must not define or leak into that contract, must
not introduce a compatibility layer, and must remain clearly displaced by the
phase gate that removes it.

## Required pre-edit conformance check

Before changing runtime code or tests, record in the working update:

1. The active roadmap phase and gate.
2. The exact governing specification sections and accepted decisions.
3. The legacy mechanisms those sections explicitly remove or prohibit.
4. A mapping from every new field, class, and public method to its specification
   requirement.

Search the design documents for every legacy concept considered for reuse. If a
new interface exists only to satisfy the current runtime, do not add it. Leave the
new contract incomplete until the roadmap reaches the mechanism that the
specification requires.

After editing, compare the diff to the recorded mapping before running tests. Use
architectural tests only when they protect a durable design boundary through
meaningful behavior. Do not add historical tests whose sole purpose is asserting
that a legacy name or implementation detail no longer exists.

## Current status

This workstream is **deferred**. Its in-progress runtime is shelved on
`v1.1/state-model`; `STATE_MODEL_HANDOFF.md` on that branch records the exact
position. Do not resume it without reading
[`../REINTEGRATION.md`](../REINTEGRATION.md) first.
