# ADR 026: A Component Session Is A Django-Session-Backed Mapping

Status: Accepted; implemented on branch

Date: 2026-10-06

Supersedes the cache-backed iteration of this decision (2026-10-05), which
never shipped.

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
flow's position, a per-user scratch value. Glue rebuilds every component from
its token on each request and has no circuit, so where a server-circuit
framework says "hold it in a private field," Glue would silently lose it
(component-system.md §2). Signing such values into the token makes them
client-visible, grows every response, and re-signs the token on every change;
a private field loses them on the next request.

The first iteration of this decision put the state in the host application's
default cache, shared by every user. Revisiting it, the motivating uses —
a multi-step flow's position, onboarding progress, per-user rate limiting —
are per-user by nature: two users running the same component need separate
values, and class-shared state was the exception, not the rule. The request's
Django session is the host application's existing per-user server store:
already wired through the middleware, already persisted, already bound to the
user. The cost the cache iteration avoided — writing for an anonymous user
creates a session row — is the same cost the host application pays for any
session use, and anonymous session churn is already an open hardening item in
`design/roadmap.md`.

## Decision

`Component.session` is a `ComponentSession`: a mutable mapping over one entry
in the request's session, scoped by the component class's qualified name and
persisted with the session when the request completes.

1. **One session entry per user, per component class.** The namespace is
   `type(component).__qualname__` and the session key is
   `DJANGO_GLUE_COMPONENT_SESSION_KEY_PREFIX` (default
   `django_glue:component_session:`) followed by the namespace. All instances
   of the class share the entry within one user's session. State shared
   across users belongs in the database or the cache.
2. **The mapping is the API.** `__getitem__`, `__setitem__`, `__delitem__`,
   iteration, and `len`, plus the `MutableMapping` conveniences (`get`, `pop`,
   `update`, `clear`). Keys must be strings; values must be serializable by
   the host's session backend (JSON for cookie sessions, pickled for the
   database session).
3. **Persistence rides on Django.** Setting a key to a value it does not
   already hold marks the session modified, and Django saves a modified
   session when the request completes, so a request that changes nothing
   saves nothing. Writes go straight into the session when they happen, so a
   call that raises does not roll back a write it made before failing.
4. **The session is not signed and never crosses the wire.** It is not part
   of the policy token, `static_data`, or `computed_data`, and it is not an
   admitted update; the client cannot read or write it. It coexists with the
   signed state model without interposing on it: the reconstruction pipeline
   is unchanged (component-system.md §4, "Hydration is framework-owned"), and
   the token remains the only authority for client-facing state.

## Consequences

- State that never crosses the wire has a home, and "no state engine" stays
  true where it matters: the signed, client-reconciled state that is the
  reactive system (component-system.md §3, overview.md objective).
- The state is per-user. The class-shared counter the cache iteration
  described now belongs in the database or the cache; a component that needs
  it must say so.
- Writing scratch state for an anonymous user creates a session row, and a
  large value grows the session cookie or row. Scratch that is large or must
  survive session expiry belongs in the database.
- The namespace is the unqualified `__qualname__`: two classes with the same
  qualified name in different modules share one entry within a session.
- A failed call keeps the session writes it made before raising; callers that
  need all-or-nothing scratch state must manage it explicitly.

## Alternatives considered

- **The default cache (the previous iteration of this record).** Class-shared
  and TTL-managed, with no session-row cost, but the motivating uses are
  per-user, it adds a second server store Glue does not otherwise use, and a
  host cache flush silently resets every component session.
- **A database table.** Durable and queryable, but a migration, a model, and
  a cleanup story for state that is scratch by definition; the session already
  provides the per-user scope and persistence.
- **Signing the values into the policy token.** Client-visible, one re-sign
  per change, and a permanent growth in every response — the cost ADR 013 and
  ADR 025 declined to grow.
- **A private field and a per-request circuit.** The server-circuit answer;
  Glue rebuilds from the token and has no circuit (component-system.md §2), so
  the field dies on the first reconstruction.
