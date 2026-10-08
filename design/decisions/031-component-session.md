# ADR 031: A Component Session Is A Django-Session-Backed Mapping

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
in the request's session, scoped by the component class's module-qualified
name and persisted with the session when the request completes.

1. **One session entry per user, per component class.** The namespace is the
   class's `module.qualname`, the same string its signed identity carries as
   `component_id`, so two classes that share a name in different modules keep
   separate entries. The session key is
   `DJANGO_GLUE_COMPONENT_SESSION_KEY_PREFIX` (default
   `django_glue:component_session:`) followed by the namespace. All instances
   of the class share the entry within one user's session. State shared
   across users belongs in the database or the cache.
2. **The mapping is the API.** `__getitem__`, `__setitem__`, `__delitem__`,
   iteration, and `len`, plus the `MutableMapping` conveniences (`get`, `pop`,
   `update`, `clear`). Keys must be strings; values must be serializable by
   the host's session backend (JSON for cookie sessions, pickled for the
   database session).
3. **Persistence rides on Django.** Setting or deleting a key marks the
   session modified, as it does on Django's own session, and Django saves a
   modified session when the request completes, so a request that writes
   nothing saves nothing. Setting a key marks the session modified even when
   the value is unchanged: comparing the old and new values cannot see a list
   or dict that was mutated in place and assigned back, and would drop that
   write. A value mutated in place without being assigned back is not saved.
   Writes go straight into the session when they happen, so a call that
   raises does not roll back a write it made before failing.
4. **The session is not signed and never crosses the wire.** It is not part
   of the policy token, `static_data`, or `computed_data`, and it is not an
   admitted update; the client cannot read or write it. Decision 5 is the
   one exception, and it is read-only. It coexists with the
   signed state model without interposing on it: the reconstruction pipeline
   is unchanged (component-system.md §4, "Hydration is framework-owned"), and
   the token remains the only authority for client-facing state.
5. **A declared value may live in the session.** `step: int =
   Glue.SessionAttr(0)`, a shortcut for `Glue.attr(0, session=True)`, declares
   a value stored in the session under its own name. Reading it returns the
   stored value or the declared default, and a read writes nothing. Assigning
   it in a callable writes the session. It is the one way a session value
   reaches the client, and only downward: it is sent as `computed_data`, the
   same role as a `Glue.property`, so it is never signed into the token and
   the client cannot write it. The session stays the only copy, so a stale
   page cannot restore an old value. `session=True` is rejected with
   `parameter`, `editable`, `render_as_html`, `skip_rerender` and
   `glue_factory`, on a method or property, and on a class that is not a
   component.

## Consequences

- State that never crosses the wire has a home, and "no state engine" stays
  true where it matters: the signed, client-reconciled state that is the
  reactive system (component-system.md §3, overview.md objective).
- Glue's protocol stays stateless between requests, as state-model.md §2 and
  [ADR 028](028-formsets-edit-saved-records.md) rely on: reconstruction,
  admission and authorization still read only the verified token, and no
  Glue object other than a component that opts in touches the session. What
  changes is that a component can now ask the host application's session to
  remember something for it.
- The state is per-user. The class-shared counter the cache iteration
  described now belongs in the database or the cache; a component that needs
  it must say so.
- Writing scratch state for an anonymous user creates a session row, and a
  large value grows the session cookie or row. Scratch that is large or must
  survive session expiry belongs in the database.
- Moving or renaming a component class changes its namespace, so its session
  state starts over, as its signed identity does.
- A failed call keeps the session writes it made before raising; callers that
  need all-or-nothing scratch state must manage it explicitly.
- A session write never decides whether a component re-renders, as a
  database write does not. A callable re-renders its component by default
  (ADR 022), and that render sends the session attributes' current values.
- A callable that does not re-render still sends a session attribute it
  wrote. The session reports each key it sets or deletes to its component,
  and a key that names a session attribute is included in that response's
  `computed_data`, whether the callable assigned the attribute or wrote its
  key through `self.session`. The markup is not rendered again, so only
  client-side bindings to the value update.
- Other mounted instances of the class share the entry and show their old
  value until they render again; one that must follow lists an event the
  writer emits in `rerender_on`.
- A session attribute is shared by every instance of its class, unlike every
  other declared value. A component stamped once per row should not declare
  one for per-row state.

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
