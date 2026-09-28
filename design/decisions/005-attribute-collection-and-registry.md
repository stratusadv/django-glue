# ADR 005: Collect Attribute Definitions Through BaseGlue

Status: Accepted; implemented on branch

Date: 2026-09-14

## Context

Attribute definitions come from two fundamentally different places. Class-body
declarations are static for an owner type and can be inspected without executing
application code. Built-in Glue families and custom adapters derive definitions
from a configured Glue instance and its external subject.

A collector hierarchy with one subclass per source pushes family adaptation out
of the `BaseGlue` subclass that owns it. A mutable registry that stages several
collectors then duplicates orchestration already owned by `BaseGlue`.

## Decision

`GlueAttributeCollector` is the single collector. It inspects class-body
declarations with `inspect.getmembers_static`, never executes application code,
and caches its result by owner type.

`BaseGlue._collect_attributes()` always combines those static definitions with
the iterable returned by `collect_attributes()`. A `BaseGlue` subclass overrides
`collect_attributes()` to describe definitions derived from its configured
instance, family metadata, or external subject. It does not call `super()` to
retain class-body declarations because `BaseGlue` includes them unconditionally.

`GlueAttributeRegistry` receives the complete iterable of definitions at
construction. It validates and indexes one immutable, path-ordered shape. It is
not a collector orchestrator or mutable builder.

The private legacy runtime collector remains only while phase 3 migrates current
consumers away from `BaseGlueAttribute`. It is not part of the new contract and
is deleted with the old attribute hierarchy.

## Consequences

- Adding a custom Glue family requires one `collect_attributes()` override, not
  a collector subclass or registration mechanism.
- Static declarations are always present and cannot be accidentally omitted by
  a family override.
- Cross-source path collisions and namespace ancestry are validated once over
  the complete definition set.
- Collection, validation, indexing, and binding have distinct ownership.
- There is no collector base class, collectors package, per-family collector,
  mutable registry staging API, or registry `collect()` method.

## Rejected alternatives

- One collector subclass per source or Glue family.
- A collector protocol or abstract base class.
- A mutable registry that stages collectors or definitions before collection.
- Requiring family overrides to invoke static collection or call `super()`.
- Retaining the legacy runtime collector as the public collector contract.

The attribute and composition contracts remain in
[`../specs/core/state-model.md`](../specs/core/state-model.md#4-addressed-objects-and-attributes-use-one-pipeline-not-one-class).
