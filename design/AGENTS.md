# Design is the source of truth

The `design/` directory is the internal source of truth for Django Glue's
redesign. This file is binding on every agent session that touches this repo.

It holds **two workstreams with different rules.** Read this file before either.

| Directory | Status | Binding rules |
| --- | --- | --- |
| [`components/`](components/) | **Active** | this file |
| [`reactive-system/`](reactive-system/) | Deferred | [`reactive-system/AGENTS.md`](reactive-system/AGENTS.md) |

## Which specification governs

**If you are working on components — the active workstream —
[`components/spec.md`](components/spec.md) governs.** It specifies a component
layer built on the wire the repository has today.

`reactive-system/component-system.md` also describes a component system. It is
**not** binding on component work. It targets a redesigned wire that does not
exist, and it is deferred. Read it for rationale; do not implement from it.
`components/README.md` tabulates where the two deliberately differ.

Using the wrong document is the most likely mistake in this repo right now. The
tell is mechanism: if you find yourself reaching for addresses, `state_snapshot`,
`effects.events`, mount-only policies, or a flat `objects` envelope, you are
reading the deferred specification.

## Build on the current wire

The component work is **deliberately built on the existing wire**, adjusting it
minimally. This is the opposite of the reactive-system rule, and it is
intentional.

- **Use the current wire's mechanisms** — `manifest_list`, `GluePolicy.identity`,
  `GlueAttributeCollector`, `GlueObjectAttribute`, `GlueTemplateResponse`,
  `GlueResponse._serialize_glue_values`. These are the substrate, not legacy to be
  migrated away from. `components/spec.md` §Context documents what each already
  provides.
- **Adjust the wire only where the spec says to.** `components/spec.md` §Wire
  adjustments lists four changes and states that there are no others. A change
  outside that list needs a specification change first.
- **Do not import the deferred wire's contracts piecemeal.** Pulling addresses or
  `state_snapshot` forward "just for this one thing" re-couples the workstreams,
  which is the coupling this split exists to remove.

## Missing beats wrong

The one rule carried over from the reactive-system side, because it is right in
both places:

**Do not reuse a legacy mechanism as a stand-in for a contract you cannot yet
implement.** If a feature needs the deferred wire, leave it unimplemented and
record it in [`REINTEGRATION.md`](REINTEGRATION.md) rather than shipping a weaker
version under the specification's name. `authorize()` is the worked example:
specified at three call points, two of which need the new wire, so it is absent
rather than partial.

This does **not** forbid building on current-wire mechanisms. The distinction is
between *using the substrate* and *misnaming a weaker thing*. `parameter=True`
mapping onto signed `identity` is fine — identity genuinely is what reconstructs
an object. A half-implemented `authorize()` is not.

## Known seams are documented, not discovered

The prototype knowingly accepts six seams — embedded children, eager child
evaluation, a DOM-liveness sweep in place of disposal, callable results without
lifecycle, hashed names in place of addresses, and a set of deliberate absences.
All are in [`REINTEGRATION.md`](REINTEGRATION.md).

If you hit one, it is expected. Do not work around it by inventing a mechanism the
deferred wire already specifies — extend the entry in `REINTEGRATION.md` if you
learn something new about it.

## Authority ladder

- [`components/spec.md`](components/spec.md) governs the active component work.
- [`REINTEGRATION.md`](REINTEGRATION.md) records what each workstream owes the
  other. It never defines protocol semantics.
- [`reactive-system/`](reactive-system/) governs the deferred workstream under its
  own `AGENTS.md`.
- When the component spec is silent on something the reactive-system documents
  cover, that is usually a deliberate deferral — check `REINTEGRATION.md` before
  assuming it is an oversight.

## If the spec is wrong

Flag it rather than deciding in favor of the existing code, and do not widen or
narrow it silently. The component spec is young; it was derived in one design pass
and will have gaps. A gap is a conversation, not a license to improvise.

Tests verify the spec. A test encoding behavior the spec contradicts should be
updated, not defended.
