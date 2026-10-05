# ADR 026: A Component Session Is A Cache-Backed, Save-On-Change Mapping

Status: Accepted; implemented on branch

Date: 2026-10-05

## Context

The signed policy token is the store for every piece of state a client sees:
`state_snapshot` and parameters in, admitted updates and a successor token out
(state-model.md §5, §10). That store is the client's. It lives as long as the
client holds it (24 hours from issuance, [ADR 013](013-policy-token-lifetime.md)),
it costs one signature per change, and its size is a cost paid on every
response — the same cost
[ADR 025](025-parent-renders-keep-mounted-children.md) refused to let grow with
the children a component holds.

Some component state sees no client at all: a rate-limit counter, a multi-step
flow's position, a per-class scratch value. Glue rebuilds every component from
its token on each request and has no circuit, so where a server-circuit
framework says "hold it in a private field," Glue would silently lose it
(component-system.md §2). Signing such values into the token makes them
client-visible, grows every response, and re-signs the token on every change;
a private field loses them on the next request.

Django already ships two server stores. The request session is per-user by
construction, cookie- or row-bound, and writing to it creates the session
eagerly — anonymous session creation is an open hardening item in
`design/roadmap.md`. The default cache is shared, eviction- and
TTL-managed by the host application, and a dependency of any Django project
already.

## Decision

`Component.session` is a `ComponentSession`: a mutable mapping over one entry
in the host application's default cache, scoped by the component class's
qualified name and persisted only when explicitly saved after a change.

1. **One cache entry per component class.** The namespace is
   `type(component).__qualname__` and the cache key is
   `DJANGO_GLUE_COMPONENT_SESSION_CACHE_PREFIX` (default
   `django_glue:component_session:`) followed by the namespace. All instances
   of the class share the entry, and all users share it. That is deliberate:
   the motivating use is component-level scratch, and per-user state belongs
   in the database or in a signed parameter. The constructor keeps the
   request, which the cache backend does not need today; it is the hook for a
   user-scoped key if the store ever earns one.
2. **The mapping is the API.** `__getitem__`, `__setitem__`, `__delitem__`,
   iteration, and `len`, plus the `MutableMapping` conveniences (`get`, `pop`,
   `update`, `clear`). Keys must be strings; values must be picklable, because
   cache backends pickle.
3. **Saving is change-only, and the component flushes.** Setting a key to a
   value it does not already hold marks the namespace dirty, and the entry is
   written only when dirty, so a request that changes nothing writes nothing.
   The component flushes the session when
   `mount()` completes at introduction and when every attribute call — a
   callable, `$receive`, or `$refresh` — completes, so application code does
   not remember to save; a call that raises never flushes, and the change is
   lost. `session.save()` persists immediately for code outside those points
   and is a no-op when clean. A component holds one session per request, so
   one request's writes cannot overwrite each other; across requests the
   store is last-write-wins.
4. **`session.discard()` deletes the entry** and forgets the local view.
5. **The session is not signed and never crosses the wire.** It is not part of
   the policy token, `static_data`, or `computed_data`, and it is not an
   admitted update; the client cannot read or write it. It coexists with the
   signed state model without interposing on it: the reconstruction pipeline
   is unchanged (component-system.md §4, "Hydration is framework-owned"), and
   the token remains the only authority for client-facing state.

## Consequences

- State that never crosses the wire has a home, and "no state engine" stays
  true where it matters: the signed, client-reconciled state that is the
  reactive system (component-system.md §3, overview.md objective).
- The host application's default cache becomes a hard dependency for the
  feature. Entries live as long as the host's cache policy dictates (TTL,
  flush, eviction), and a cache flush silently resets every component session.
- The entry is shared across instances and across users. Concurrent requests
  to the same class race with last-write-wins and no locking. A value that
  must be per-user, or must survive a flush, belongs in the database.
- The namespace is the unqualified `__qualname__`: two classes with the same
  qualified name in different modules share one entry.
- Values pickle rather than serialize to JSON; a host cache configured for a
  JSON wire breaks values that do not JSON-serialize.

## Alternatives considered

- **The Django session (`request.session`).** Per-user by construction, so it
  cannot express a class-shared slice; every write creates a session row, and
  anonymous session churn is an open hardening item; cookie and database
  session size limits bite a shared counter.
- **A database table.** Durable and queryable, but a migration, a model, and a
  cleanup story for state that is scratch by definition; the cache already
  provides eviction.
- **Signing the values into the policy token.** Client-visible, one re-sign
  per change, and a permanent growth in every response — the cost ADR 013 and
  ADR 025 declined to grow.
- **A private field and a per-request circuit.** The server-circuit answer;
  Glue rebuilds from the token and has no circuit (component-system.md §2), so
  the field dies on the first reconstruction.
- **A user-scoped cache key (namespace plus user id).** Available later
  without a breaking change because the request already travels to the
  constructor; declined for now because the motivating uses are class-shared
  and per-user state has the database.
