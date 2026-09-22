# Component System

Status: **Active workstream.** Design accepted; implementation pending.

This directory is the source of truth for the component work on
`v1.1/components`. It specifies a component layer built on the wire the
repository has today.

## Reading order

1. [`spec.md`](spec.md) — the component specification: registration, stamping,
   parameters, mounting, composition, rendering, and lifecycle.
2. [`../REINTEGRATION.md`](../REINTEGRATION.md) — the seams this prototype
   accepts and how it meets the deferred state model later.

## Relationship to `reactive-system/`

[`../reactive-system/`](../reactive-system/) specifies a redesigned state model
and wire format. **That work is deferred** and its runtime lives on
`v1.1/state-model`.

`reactive-system/component-system.md` describes the component system as it will
exist *on that new wire*. It remains the long-term target and is worth reading
for rationale — the Blazor/Livewire split, the parameter contract, morph
boundaries, keys — but it assumes contracts (addresses, `state_snapshot`,
`effects.events`, the flat `objects` envelope) that do not exist.

**For anything on this branch, [`spec.md`](spec.md) governs.** Where the two
documents describe the same feature differently, `spec.md` states the difference
and why. The largest ones:

| Topic | `reactive-system/component-system.md` | `spec.md` |
| --- | --- | --- |
| Stamping | `<glue:time-entry-day />` elements, compiled by a `DjangoTemplates` subclass | `{% glue_component %}` Django template tag |
| Composition | every object an independent addressed island | declared children embed; stamped components are flat |
| Identity | opaque addresses derived from owner, path, family, key | generated names hashed from parent, tag name, key |
| Events | declared events, `$on()`, `effects.events` | not implemented |
| Refresh | `$refresh()` on every addressed object | not implemented |

## What this prototype targets

Three of the five problems in the component design's context section: hand-written
child identity strings, template inputs carrying the text of a JavaScript
identifier, and replacement destroying Alpine scopes. The remaining two —
stringly-typed invalidation and the missing mount signal — need `$refresh()` and
declared events, and are deferred with them.

## Gate

A parent component stamping N keyed children, each owning server state, surviving
a morph — proven by an E2E test in `test_project` built around a port of the
time-entry dashboard. See [`spec.md`](spec.md) §Gate.
