# ADR 044: A Call Answers The Receivers Of Its Events

Status: Accepted

Date: 2026-11-18

## Context

ADR 024 and ADR 039 deliver an event a call emits to the components that react
to it: those whose `rerender_on` names it, and an ancestor whose listener does.
The server is stateless and does not know which components are on the page, so
the client learned of the event from the call's response and then sent a second
request, a `$receive` to each reacting component. A save in a modal therefore
took two requests in a row: the save, then the re-render of the list or detail
card behind the modal.

The second request repeats every request's fixed work (middleware, the session
and user, each token) and adds a network round trip. Showcase is the project
that reacts to events: 22 components list a `saved`, `deleted`, `added` or
`imported` event in `rerender_on`, and each save of one of its 24
event-declaring modals woke one or two of them. Measured on showcase's customer
Edit modal:

| | Requests | Localhost | 100 ms per request |
|---|---|---|---|
| Delivered in a second request | 2 | 50 ms | 255 ms |
| Answered in the call's response | 1 | 41 ms | 139 ms |

The client knows, before a call, which mounted components would react to an
event the called object declares: the object's `event_ids` and each
component's `rerender_on` and `listeners` are in their static data, and the
client already matched them after the response. Only whether this call emits is
unknown until it runs.

## Decision

**A call names the mounted objects that would react to an event its object
declares, and the server answers them in the call's own response.**

1. The client attaches `receivers` to a call's request entry: each mounted
   object whose static data reacts to an event the called object's class
   declares, with its address, token, unsaved changes, mounted children and
   child submissions, as its own `$receive` would send them. A refresh, a call
   answered when its object was introduced (ADR 043), and a call inside the
   `$receive` batch carry none. A receiver with a call queued or running is
   left out, as is one with files to upload.
2. After the call succeeds, the resolver builds the deliveries itself, from
   the events the call emitted and the token it issued. The client names no
   event and supplies no detail, so a receiver hears only what the call did.
3. The receiver's class says which of those events it reacts to, from its
   declarations and without being rebuilt: `BaseGlue.reacting_events()` answers
   none, and `Component` answers its `rerender_on` events and, when the source
   names it as an ancestor, its listeners'. A receiver that reacts to none is
   not answered.
4. Each reacting receiver is then resolved as a requested `$receive` entry is:
   its token is verified and bound to the session and user, the call hooks run
   (ADR 035), and `_receive` authorizes and runs its listeners and re-renders
   it. A refusal is that receiver's error entry.
5. Each receiver is resolved in its own savepoint. An unexpected exception in
   one is logged and becomes its error entry: its writes are undone, and the
   call, with what it wrote, stands, as it did when the receiver had a request
   of its own.
6. The response lists the call's entry and the objects it introduced, then
   each answered receiver's entry and the objects its render introduced. The
   client applies a receiver's answer through that receiver's own call queue,
   as the response to its `$receive`, with the state the receiver was sent in.
   A receiver the response did not answer, answered with an error, or changed
   by another call since it was sent is delivered to with a `$receive` request
   as before. Events a receiver's own re-render emits travel as before.

A receiver's address may not repeat an address the request names: the
envelope refuses it with `duplicate_addresses`.

## Consequences

- A save whose event other components react to costs one request instead of
  two.
- A call to an object that declares events uploads its receivers' tokens even
  when it emits nothing. In showcase that is one or two receivers, about
  1.5 to 3 KB, on the 6 of 30 callables of event-declaring components that
  never emit, and on a save its form refuses. A page with many reacting
  components pays more on every such call; none exists.
- The receivers' tokens are ones the browser already holds and sends with
  their own calls. A receiver is never answered for an event the call did not
  emit, and the client can no longer relay an event detail the call did not
  produce for one that is answered.
- A receiver is answered inside a database savepoint, so the resolver needs
  the default database for any call that names one.
- Glue's own `$receive` request remains for a receiver the response did not
  answer and for events from a receiver's re-render, so a response from a
  server that does not answer receivers works unchanged.
- A browser test that waited for a `$receive` request after a call now times
  out. It waits for what the user sees instead, such as the re-rendered list.

## Rejected Alternatives

- **Declaring which callables emit which events**, as an option such as
  `@Glue.attr(emits=...)`. It would spare the receivers on calls that never
  emit, but every emitting callable would have to declare it, a missed one
  would silently fall back to two requests, and it is an option on the general
  `Glue.attr` that only event-emitting callables use.
- **Reading which events a callable emits from its body.** An event emitted
  from a helper, a service, `super()` or by name at runtime would be missed,
  and a miss silently falls back to two requests.
- **Falling back to the second request above some number of receivers.** It
  would protect a page with many reacting components, which no project has,
  at the cost of two mechanisms for one delivery.
