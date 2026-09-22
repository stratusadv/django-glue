# ADR 006: Name the BaseGlue Hook `get_extra_attributes`

Status: Accepted for the redesign; implementation in progress

Date: 2026-09-14

Supersedes: ADR 005's public hook name only

## Context

ADR 005 placed family-derived attribute definitions on `BaseGlue` through a
`collect_attributes()` hook. Static class-body collection is already performed
unconditionally by the private assembler, so the public hook does not collect
the complete attribute shape. Its name obscures that distinction.

## Decision

The overridable hook is named `get_extra_attributes()`. It returns definitions
derived from the configured Glue instance, family metadata, or external subject.

`BaseGlue._collect_attributes()` remains the private complete-shape assembler. It
combines the static `GlueAttributeCollector` result with
`get_extra_attributes()` before constructing the immutable registry.

All other decisions and consequences in ADR 005 remain accepted.

## Consequences

- A subclass override describes only the definitions additional to its static
  class-body declarations.
- Static definitions remain unconditional and cannot be omitted by an override.
- The public name no longer implies that the override owns complete collection.

## Rejected alternatives

- Keeping `collect_attributes()` despite its narrower responsibility.
- Naming the hook `get_attributes()`, which would imply that it returns the
  complete attribute shape.
