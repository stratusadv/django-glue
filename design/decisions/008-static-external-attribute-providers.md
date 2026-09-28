# ADR 008: Separate Static External Providers from Extra Declarations

Status: Accepted; implemented on branch

Date: 2026-09-15

Supersedes: ADR 007's treatment of statically declared external-provider attributes

## Context

ADR 007 made every external attribute source a provider/declaration-map pair.
That is necessary for imperative family metadata and custom adapters, but it
duplicates static inspection when a wrapped model, form, queryset, or formset
already declares attributes on its class body.

Those declarations have the same invariant shape as declarations on a
`BaseGlue` subclass. Only their binding owner differs.

## Decision

`get_attribute_providers()` returns an iterable of explicitly selected external
provider instances. `GlueAttributeCollector` reuses its cached static
definitions for each provider type and binds every resulting path to that
provider instance.

`get_extra_attributes()` remains the provider/declaration-map interface from
ADR 007, but it is reserved for declarations assembled imperatively from
configured family metadata or custom adapter logic.

`GlueAttributeCollector` is stateless. Its collection entry points receive the
owner type, provider iterable, or extra-attribute groups directly. Explicit
provider selection does not permit recursive object-graph discovery.

## Consequences

- Static inspection and compilation occur once per declared owner type.
- Django Glue families identify wrapped providers without reimplementing
  `inspect.getmembers_static`.
- Imperative fields remain bound to the provider named by their declaration
  group.
- The old runtime collector may temporarily consume the same provider hook, but
  does not define its new semantics.

## Rejected alternatives

- Re-inspecting and recompiling provider class bodies inside every family hook.
- Treating an empty declaration mapping as an implicit request for discovery.
- Automatically walking arbitrary provider graphs.
