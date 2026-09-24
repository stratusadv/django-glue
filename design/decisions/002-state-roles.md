# ADR 002: Separate Value Roles from Construction Parameters

Status: Accepted; implemented on branch

Date: 2026-09-10

## Context

Glue currently spreads identity, mutable state, loading, metadata, and response
behavior across separate flags and family-specific implementations. A signed
read-only value can presently be overwritten through client hydration, and
components would otherwise inherit the same ambiguity.

## Decision

Developers declare what a value is, and Glue derives direction, protection, and
timing. There are three value roles:

- A `Glue.attr` without `editable=True` is a reconstructor. It has signed
  continuity and the client cannot write it.
- A `Glue.attr(..., editable=True)` is editable state with an admitted,
  untrusted update channel.
- A `@Glue.property` is recomputed derived output and never travels upward.

Construction exposure is a separate dimension. `parameter=True` makes either a
reconstructor or editable-state declaration part of the generated constructor
and initial mounting contract. It does not determine the declaration's role.
Parameterized values live in `target.parameters`; retained non-parameterized
reconstructors and editable state live in `state_snapshot`.

The signed policy token contains target parameters, retained state, a shallow
owner-path-to-child-address map, capability, subject binding, and temporal
constraints. Child policies and state are never nested. Responses return a
successor token plus complete `unsigned_data`; the client computes the actual
patch through three-way reconciliation and preserves newer local edits.

The model applies equally to components, custom objects, models, forms,
querysets, formsets, sequences, and functions.

## Consequences

- `takes_client_state`, `updates_client_state`, `identity=True`, and the existing
  loading-strategy state semantics are removed.
- Signing establishes continuity, not domain validity, confidentiality,
  freshness, or permission by itself.
- Current declarations and authorization narrow every signed capability on each
  request.
- Construction exposure can be chosen independently from client editability;
  `parameter=True, editable=True` is a supported combination.
- Form and model adapters can retain invalid drafts without treating them as
  persisted domain truth.

## Rejected alternatives

- Public `signed=`, `locked=`, or direction-enum declarations that expose
  transport mechanics instead of value roles.
- Round-tripping the entire client-facing object as Livewire does; derived
  output and schema are not consumed upward by Glue.
- A second state engine specifically for components.

The complete contract remains in [`../specs/core/state-model.md`](../specs/core/state-model.md).
