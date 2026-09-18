# Internal Design Work

These documents are working architecture material and are not part of the
published documentation site.

Read [`AGENTS.md`](AGENTS.md) first — it says which specification governs which
work, and the two workstreams below have different rules.

- [`components/`](components/) — **active.** The component system, built on the
  current wire: registration, template-tag stamping, parameters, mounting,
  composition, and morph-based rendering.
- [`reactive-system/`](reactive-system/) — **deferred.** The state-model and wire
  redesign: value roles, addressed objects, schema, transport, and reconciliation.
  Its in-progress runtime is shelved on `v1.1/state-model`.
- [`REINTEGRATION.md`](REINTEGRATION.md) — where the deferred work stands, why it
  was set aside, the seams the component prototype accepts, and the plan to bring
  the two back together.
