# ADR 024: A Component Declares the Descendant Events It Reacts To with `rerender_on` and `Glue.listener`

Status: Accepted; implemented on branch

Date: 2026-09-29

Amended 2026-09-29, before release: a re-render with no code to run is declared
with the `rerender_on` class attribute instead of an empty `Glue.listener`
method. See "Declaring a re-render".

Partly superseded by [ADR 025](025-parent-renders-keep-mounted-children.md): a
component's re-render keeps its mounted children instead of re-stamping them,
`rerender_on` is delivered page-wide rather than to ancestors only, deliveries
are batched, and the source always applies its own morph. A stamped child's
address now also carries a hash of the parameters and access its stamp passes,
so the statement below that addresses are "not from parameters" no longer holds
for stamped children. The ancestor chain is unaffected: it holds the parent's
address, a child the parent stamps with new parameters is a new child with the
same parent, and a child that retargets its own model parameter keeps its
address, because only a stamp computes the hash.

## Context

A rendered component can already announce an outcome. It declares
`saved = Glue.event()`, emits it from a successful callable, and the response
carries it in `effects.events`. The client then delivers it to `$on()`
listeners on the source proxy and dispatches a bubbling DOM `CustomEvent` from
the source's root (`component-system.md` §7, `state-model.md` §6).

What a component cannot do is declare that it reacts to a descendant's event.
When a child's action changes something its parent renders, the parent's
template wires the dependency in markup:

```django
<section @confirmed="component.$refresh()" @merchant-rule-created="component.$refresh()">
    {% for transaction in transactions %}
        {% glue_component 'banking/transaction_row' transaction=transaction key=transaction.pk %}
    {% endfor %}
</section>
```

This works, but it has three problems:

- **The dependency is invisible in Python.** A reader of the parent component's
  class cannot see that it depends on its rows. The event names are strings in
  a template, checked by nothing.
- **Nothing ties the listener to the child's declaration.** Renaming the child's
  event silently breaks the parent.
- **The screen is briefly inconsistent.** The child's response morphs the row,
  and the parent's refresh morphs the summary one round trip later. In between,
  a confirmed row sits beside a stale "N to confirm" count.

The Profitly transaction review shows why this matters. Confirming one
transaction changes the row, the month summary, and the rule offer on every
other row from the same merchant. The page therefore keeps every action on the
list component and passes an unsigned `transaction_id` that each action
re-scopes. A row component with a model parameter (ADR 021) would sign the
row's identity and let a row in a closed month be built with `VIEW` access, but
only if the list can react to what the row did.

Comparable frameworks put the listener on the listening component's class:
Livewire's `#[On('confirmed')]`, and Blazor's `EventCallback` parameter. Livewire
is stateless per request, as Glue is, and delivers a server-dispatched event in
the browser, where the listening component makes its own request. Blazor and
LiveView handle it in the same server step because they keep components alive
on the server, which Glue deliberately does not.

## Decision

### Declaring a re-render

The common case has no code to run: the component shows something its children
change, and must re-render when they announce it. It declares that as class
configuration, beside `template` and `layout_template`:

```python
class TransactionReviewComponent(SignedInComponent):
    template = 'banking/component/transaction_review.html'
    rerender_on = (
        TransactionRowComponent.confirmed,
        TransactionRowComponent.merchant_rule_created,
    )
```

`rerender_on` is a tuple of declared events, checked when the class is defined.
The name states the effect and the trigger, so a reader does not need to know
how delivery works to see why the component renders again. A subclass replaces
or extends the tuple.

The first version of this ADR expressed the same thing as a `Glue.listener`
method with an empty body. That is a declaration dressed as a method: the
decorator needed something to attach to, and nothing in the snippet said that a
re-render follows. A bodiless `Glue.listener(...)` class attribute and a
`Glue.depends_on(...)` were also considered and rejected for the same reason,
and `depends_on` suggests a data dependency such as a model more than an event.

### Declaring a listener

`Glue.listener(*events)` decorates a component method that runs when one of the
events arrives. Each argument is a declared event, referenced through the class
that declares it. The component then re-renders under the same rule as any
component callable.

- **Only a component may declare a listener or `rerender_on`.** Re-rendering is
  what they are for, and only components render. Declaring a listener on
  another Glue object is an error at class definition, as
  `Glue.ComponentParameter` is.
- **Events are referenced as objects, not names.** `GlueEvent` records the class
  that declares it, so a misspelled event fails at import. An event fired by
  name with `Glue.event(obj, 'saved', {...})` has no declaration and cannot be
  listened to.
- **A subclass's inherited event matches.** An event's identity is its declaring
  class and name, so a listener on `TransactionRowComponent.confirmed` also
  receives it from a subclass of the row.
- **The handler may take the event.** Add a `Glue.ReceivedEvent` parameter to
  read its name, its detail, and its source. Omit the parameter to only react.
- **`event.source` is the component that emitted the event.** It is rebuilt
  from the source's signed token as it stands after the action that emitted
  the event, so a model parameter's initializer re-applies its scope and
  `mount()` does not run again. It is rebuilt on first access, so a listener that
  never reads it pays nothing. `Glue.ReceivedEvent[TransactionRowComponent]`
  types it; a listener for events from several classes uses a union.

```python
@Glue.listener(TransactionRowComponent.confirmed)
def row_confirmed(self, event: Glue.ReceivedEvent[TransactionRowComponent]) -> None:
    self.last_confirmed_merchant = event.source.transaction.merchant
```
- **`required_access` and `skip_rerender` are accepted,** with their `Glue.attr`
  meanings. A listener returns `None`.

### Delivery

Delivery follows the Livewire model: the client routes the event to the
listening components and calls them in a second request.

1. **A component's ancestry is signed.** A component's signed identity carries
   its ancestors' addresses, nearest first. A component stamped by
   `{% glue_component %}` inherits the chain of the component whose template
   stamped it. A component returned by a callable inherits the chain of the
   component whose callable returned it. A component served by `as_view()` or
   `as_page()` has none. Addresses are derived from the parent's address, key
   and tag, not from parameters, so the chain stays valid across re-renders
   and model parameter retargeting.
2. **Listeners are published.** A component's `static_data` lists the identities
   of the events in its `rerender_on` and its listeners under `listeners`, and
   maps each event it can emit to its
   identity under `event_ids`. The client reads the ancestor chain from the
   policy payload it already decodes.
3. **The client routes by ancestry.** When a response carries an event from a
   component, the client selects each component in the source's ancestor chain
   that is mounted and has a listener for that event. Routing does not follow
   the DOM, so an Alpine `.stop` on an intermediate element does not block it,
   and a modal returned by a row's callable reaches the row's listeners even
   when its host mounts it at the end of `<body>`.
4. **One call per listening ancestor delivers its events.** The client calls
   the built-in `$receive` callable on each listening ancestor, concurrently,
   with that ancestor's events from the originating response in order, each
   with its identity, detail, and the source's current policy token. The wire
   format is unchanged: `$receive` is an ordinary call on the ancestor's own
   address and policy token, and goes through the ancestor's own call queue, so
   it is ordered after the ancestor's in-flight calls and is reintroduced
   through its owner when its token has expired, like any other call.
   Application attribute paths cannot begin with `$`, so `$receive` cannot
   collide with one.
5. **The server checks each source, runs every matching listener, then renders
   once.** For each event, `$receive` verifies the source token and rejects it
   unless the listening component's address is in the source's signed
   ancestor chain and the source's class declares or inherits the event. It
   runs the listening component's matching listeners in declaration order,
   checking each one's `required_access` and `is_authorized()` as a call to that
   listener. The first access to `event.source` rebuilds the source and checks
   its own `is_authorized()` for a read. The listening component then re-renders
   once for the whole batch when a delivered event is in its `rerender_on`, a
   listener that ran does not declare `skip_rerender=True`, or a retained value
   changed. An event the component neither re-renders on nor listens for is
   rejected.
6. **Events from listeners keep going up.** A listener may emit the listening
   component's own events. They arrive in the `$receive` response and are
   delivered to that component's ancestors in turn.

The existing channels are unchanged. The client still delivers each event to
`$on()` listeners on the source and dispatches the bubbling DOM event, so
templates that refresh by hand keep working.

### One frame on screen

When an originating response carries an event that a mounted ancestor listens
for, the client applies that response's state immediately but holds its HTML
morph until every `$receive` call settles. A listening ancestor that
re-rendered already contains the source's new markup, so the source's own morph
is skipped. When no listener re-rendered, or a `$receive` call failed, the
source morphs itself at that point, and a failure is reported on the
ancestor's address like any other per-address failure. The source's call
resolves after its listeners have been applied.

### Trust

An event grants no authority, as `state-model.md` §6 already states. `$receive`
is callable by any client holding the ancestor's token, with any event detail,
so the detail is untrusted input, exactly like callable arguments.

The source is not. `event.source` is a genuine, authorized instance of the
declared class, and its signed ancestry proves the listening component stamped
it, directly or through its descendants, or that it was returned by one of
their callables. A listener that needs to know which row changed reads
`event.source`, not a key in the detail. A client can still send `$receive`
with any source token it legitimately holds that passes those checks, so a
listener must not treat a delivery as proof that the source's action just ran.
Listeners that only re-render never read either.

## Consequences

- A component's dependencies on its descendants are declared on its class,
  checked at import, and visible where the rendering code is.
- A listener identifies the child that changed through a signed reference, so a
  parent never re-scopes a client-supplied key to find it.
- Every component's signed identity grows by its ancestor chain, typically one
  or two addresses.
- A listener's re-render re-stamps the children in its template, and a
  re-stamped child is introduced and mounted again. A child keeps only what its
  parameters and the database give it, so a counter holding a click count in
  retained state resets to its mounted value. This is how `$refresh()` on a
  parent already behaves; listeners make it happen after a child's own action.
  Children whose state lives in the database, such as transaction rows, are
  unaffected.
- A child component produced by a `@Glue.property` does not carry ancestry, so
  its events are not delivered to listeners. Stamped and returned components
  cover the cases this ADR was written for.
- Rows and other children can be components with signed identities and their own
  access, while the list that summarizes them stays consistent. The Profitly
  transaction review can move `confirm`, `always_categorize_merchant` and
  `attach_receipt` onto a row component with a model parameter, and drop
  `_transaction_in_month`.
- Each listened-to event costs one extra request, and the listener's render
  re-renders the whole parent, including every child stamped in its template.
  Declaring a listener means asking for that render. A page that cannot afford
  it splits the dependent summary into its own component and listens there.
- The screen changes once per action, not twice.
- `component-system.md` §7, `state-model.md` §6 and §10, the events guide and the
  changelog describe listeners, `$receive`, and the deferred morph.

## Alternatives considered

- **Deliver in the originating request.** The client would send each listening
  ancestor's token with every descendant call, and the server would run the
  listener and render both in one response. That saves one round trip, but it
  needs a new entry kind, cross-address event delivery on the server, and the
  parent's token verified and authorized on every descendant call even when no
  event fires. It would still need this ADR's delivery for events from objects
  outside the batch. The application code is identical, so it can be added
  later as a transport optimization if a page needs it.
- **Keep template wiring (`@confirmed="component.$refresh()"`).** Keeps working,
  and is the only option for a listener that is not a component. It leaves the
  dependency in markup and the screen briefly inconsistent.
- **Route by DOM ancestry.** Matches how the bubbling DOM event travels, but a
  modal mounted outside the listener's root would never be delivered, an
  Alpine `.stop` could block a server dependency, and the server could not check
  where the source sits.
- **Sign only the immediate parent.** Enough for a parent, but a grandparent
  listening to a grandchild could not be checked without the intermediate
  component's token.
- **Sign event payloads so listeners can trust the detail.** That would
  contradict "an event grants no authority", add a token type, and protect data
  a listener can read from its own scope anyway.
- **Listen for a descendant's successful call instead of its events.** This
  would let a component react to a call through a model's `Glue.namespace`
  service, which has no way to emit events. It is deferred. The component case
  is the one the transaction review needs, and events keep the child in control
  of what it announces.
- **String event names (`Glue.listener('confirmed')`).** Matches DOM listeners,
  but would match every descendant emitting that name and fail silently on a
  rename.
