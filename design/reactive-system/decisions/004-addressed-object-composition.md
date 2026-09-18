# ADR 004: Compose Addressed Objects Through Explicit Children

Status: Accepted for the redesign; implementation pending

Date: 2026-09-12

## Context

Glue currently uses `BaseGlueAttribute` subclasses for values, callables,
fields, and nested Glue objects. Recursive provider discovery and nested policy
payloads blur three different concepts: ordinary attribute data, structural
callable paths, and independently authorized Glue objects. Collapsing attributes
into `BaseGlue` would deepen that confusion because a field or callable does
not need an address, reconstruction contract, policy, request queue, or client
lifecycle.

The redesign must retain fluent APIs such as
`model.services.factory.duplicate()` and `model.form.save()` across components,
models, forms, querysets, formsets, sequences, functions, and custom objects.

## Decision

`BaseGlue` remains the boundary for an independently addressed runtime object.
Values, fields, properties, callables, and callable namespaces compile into
lightweight attribute definitions and never subclass `BaseGlue`.

Composition uses two explicit mechanisms:

- `Glue.namespace(provider)` groups root-owned callable paths without creating
  state, an address, a policy, or a lifecycle. `Glue.attr(...)` remains
  state-only.
- A Glue-object-typed `@Glue.property`, an equivalent built-in adapter, a keyed
  collection, or a directly declared callable result introduces an addressed
  child with its own policy and lifecycle.

Every live child has one owner, and the page-rooted ownership graph is acyclic.
The owner's signed token carries only a shallow `children` map from canonical
paths to addresses, never child policy or state.
Transport uses a flat `objects` collection. The client registers introduced
addresses before binding references, preserves a child when its path and
address remain the same, and disposes it when the owner removes or replaces
that binding.

Ordinary containers are never recursively searched for Glue objects. Raw
Django objects are never promoted automatically. A future explicit
`Glue.dict(...)` addressed family may opt a dictionary into mixed value/child
composition without weakening either rule.

## Consequences

- Parent and child reconstruction, authorization, state, request queues, and
  proxy reconciliation remain independent.
- A parent refresh cannot overwrite a child's newer draft merely by repeating
  its address.
- Dotted client syntax does not reveal the policy boundary: schema and child
  references route each operation.
- `BaseGlueAttribute`, `GlueObjectAttribute`, recursive nested-policy decoding,
  and per-family child caches are replaced by the attribute registry, address
  registry, child binder, and response dispatcher.
- A child mutation does not implicitly refresh its owner. Causal follow-up is a
  subsequent request; an atomic cross-object transition belongs to one
  callable.

## Rejected alternatives

- Collapse every attribute into `BaseGlue`; most attributes have no independent
  authority or lifecycle.
- Use `Glue.attr(...)` for service providers or nested Glue objects; this makes
  state declarations change meaning based on runtime type.
- Recursively discover decorated providers or Glue objects in arbitrary Python
  object graphs and containers.
- Embed child policies or state in owner tokens; this duplicates authority and
  makes token size grow with tree depth.
- Infer owner refreshes from nesting or ORM writes; dependencies remain
  application-specific and explicit.

The complete contracts remain in
[`../state-model.md`](../state-model.md#4-addressed-objects-and-attributes-use-one-pipeline-not-one-class)
and
[`../component-system.md`](../component-system.md#composition-mechanisms).
