# ADR 007: Declare Extra Attributes in Provider Scopes

Status: Accepted for the redesign; implementation in progress

Date: 2026-09-14

Supersedes: ADR 005's direct-definition extension API

## Context

ADR 005 made `GlueAttributeDefinition` the return type of the family extension
hook. That record is an internal compiled shape with binding and validation data;
requiring application and family authors to construct it exposes compiler
machinery as public API.

Class-body declarations already express attribute roles through `Glue.attr`,
`Glue.property`, and `Glue.namespace`. Dynamic family declarations lack only the
provider instance and the attribute names that a class body normally supplies.

Provider instances cannot safely be dictionary keys. Unsaved Django model
instances, among other valid providers, are unhashable.

## Decision

`get_extra_attributes()` returns an iterable of `(provider, attributes)` pairs.
Each `attributes` value is a mapping from an exposed path to an ordinary
`Glue.attr`, `Glue.property`, or `Glue.namespace` declaration.

The collector combines the provider and mapping key with each declaration and
compiles the result into internal `GlueAttributeDefinition` records. The
registry retains the provider binding for each compiled path. Neither family nor
application code constructs definitions directly.

The pair is deliberately not wrapped in a public helper class or factory. The
collector normalizes and validates it internally.

## Consequences

- Static and dynamic attributes use one declaration vocabulary.
- The `Glue.attr`, `Glue.property`, and `Glue.namespace` parameter lists do not
  acquire a second dynamic form.
- One hook may return attributes from any number of provider instances.
- Unhashable providers work without identity wrappers.
- `GlueAttributeDefinition` remains an internal transport between collection,
  validation, and binding.

## Rejected alternatives

- Returning `GlueAttributeDefinition` from application or family code.
- Overloading `Glue.attr` with a second parameter set for dynamic definitions.
- A dictionary keyed by provider instances.
- A mandatory public scope dataclass, named tuple, or `Glue.attributes()`
  wrapper.
