# ADR 039: Any Glue Object's Declared Events Reach `rerender_on`

Status: Accepted

Date: 2026-11-10

Supersedes part of [ADR 024](024-component-listeners.md): its delivery
section's "when a response carries an event from a component". The rest of
ADR 024 and [ADR 025](025-parent-renders-keep-mounted-children.md) stand.

Number 038 is taken by the 1.4.0 line's callable-argument record; this record
ships in 1.3.1.

## Context

ADR 024 let a component declare the events that re-render it, and ADR 025 made
`rerender_on` page-wide: any mounted component that lists an event re-renders
when any mounted component emits it. The events guide promises exactly that,
"`rerender_on` hears the event from anywhere on the page", with a summary panel
beside a list's rows as the example.

Only a component's events were delivered. The relay lived on the client's
component proxy, and `$receive` refused a source whose token was not a
component's. A form, model or queryset that declares an event, which
`component-system.md` §7 already allows ("a successful form or model `saved`
event"), could fire it to its own `$on()` listeners and nowhere else.

A Spire task list showed the gap. Its header is a summary component that
counts tasks and declares
`rerender_on = (TaskForm.saved, TaskDeleteConfirmationComponent.confirmed)`.
Deleting a task updated the counts, because the confirmation is a component.
Saving a task did not: `saved` is declared on the Django form and fired by the
`FormGlue` inside Spire's form component. The only way through was template
wiring, a script in the form's template re-raising the form's event as one
declared on the form component, which is what ADR 024 introduced `rerender_on`
to replace.

Nothing in ADR 024 or 025 argues that only components may be sources. ADR 024
was written for a row component and its list, and its listener rules need the
source's signed ancestry, which only a component carries. Page-wide
`rerender_on` needs no ancestry: the server checks only that the source token
is genuine and that the source declares the event.

## Decision

**Any Glue object's declared events reach the components that re-render on
them.** Listeners are unchanged: they still hear only their descendants, and
only a component has ancestors.

1. **Every Glue object publishes its events' identities.** `static_data`
   carries `event_ids`, each declared event's name mapped to its identity, for
   the events on the object's class and its attribute providers' classes: a
   form's on its Django form class, a model's on its model, a queryset's on its
   queryset class. Components already published it; the base class now does.
2. **The client relays from every proxy.** After a response is reconciled, any
   proxy delivers its events to each mounted component that re-renders on or
   listens for them, through `$receive`, as ADR 024 describes. A proxy's
   `$dispatch` reaches the same components a fired event does.
3. **`$receive` accepts any Glue object as a source.** The source token must
   still be genuine and issued to this session and user, and the source must
   declare or inherit the event. Each Glue class names the classes that declare
   its events from its signed identity, without rebuilding the object, through
   `event_declaring_classes(policy)`. A source that is not a component names no
   ancestors, so its events re-render `rerender_on` components and are refused
   for listeners, as a non-descendant's events always were.
4. **An event assigned to a second class keeps its identity.** A `GlueEvent`
   takes its name and identity from the class that declares it. Assigning the
   same event object to another class attribute used to rename it in place;
   it now leaves it as it was.

## Consequences

- A summary that shows what a form or model changes declares the dependency on
  its class, as for a component's events, with no template wiring.
- Each re-rendering component still costs one `$receive` request per response
  that fires a listed event, batched with the others.
- `event.source` for a listener is still always a component.
- An application can now be re-rendered by an event fired from any object the
  user holds a token for. That was already true of `$dispatch` on a component:
  an event grants no authority, and a component that re-renders reads what it
  shows from the database.
- `component-system.md` §7, the events guide and the changelog describe
  non-component sources.

## Alternatives considered

- **Keep template wiring.** It works with no Glue change, but it is the markup
  dependency ADR 024 set out to remove, and it reaches through Spire's form
  component's internal shape (`component.model.form`).
- **Re-fire form events from the owning component.** Spire's form component
  could declare `saved` and re-emit its form's. That fixes one case in one
  library, and every other object's events would stay unreachable.
- **Let listeners hear any object.** A form or model token carries no
  ancestry, so the server could not check that the source is a descendant.
  Giving them one, or borrowing the owning component's, is a larger change
  with no current use.
