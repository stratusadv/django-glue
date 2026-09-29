# Declared events

A Glue object can emit a named outcome from an authorized action. Declare the
event on its class and emit it while handling the action:

```python
from django_glue import Glue


class EntryEditor(Glue.Component):
    template = 'entry/editor.html'
    saved = Glue.event()

    @Glue.attr
    def save(self):
        entry = save_entry()
        self.saved(pk=entry.pk)
        return entry.pk
```

The event appears in that address's `effects.events` only when the action
succeeds. Its detail must be serializable. `$address` is reserved for the source
address and cannot be supplied by the action.

When no client needs a stable name, fire the event by name instead of declaring
one: `Glue.event(self, 'saved', {'pk': entry.pk})`. It validates the name the
same way a declaration does and lands in the same `effects.events` channel.

Subscribe to the source proxy with `$on(name, callback)`:

```javascript
const stop = editor.$on('saved', event => {
    console.log(event.detail.pk)
})

stop()
```

`$on()` rejects names the object did not declare and returns an unsubscribe
function. Disposal removes its listeners. Each event is delivered after the
response has reconciled the source state and introduced objects.

When the source is a rendered component, Glue also dispatches a bubbling DOM
`CustomEvent` from its current root. Its `detail` contains the declared values
and `$address`; `event.source` is the source proxy. Ordinary Alpine or DOM
listeners can observe it:

```html
<div @saved="console.log($event.detail.pk)">
    {% glue_component 'entry-editor' entry_id=entry.pk key=entry.pk %}
</div>
```

The `{% glue_component %}` tag takes Django expressions for parameters, `key`,
and `access`. Event handlers belong on ordinary markup or on the source proxy.
An ancestor DOM listener sees bubbling events from every descendant, so inspect
`$event.detail.$address` when it needs a specific child. `$on()` is always
source-scoped, including for non-rendered models, forms, and querysets.

## Reacting to a child's event on the server

A component that shows something its children change declares which of their
events re-render it, instead of wiring `$refresh()` into its template:

```python
class TransactionReviewComponent(Glue.Component):
    template = 'banking/component/transaction_review.html'
    rerender_on = (
        TransactionRowComponent.confirmed,
        TransactionRowComponent.merchant_rule_created,
    )
```

When a row stamped in this component's template emits `confirmed`, the client
delivers the event to this component, which re-renders. The row's own markup is
updated by that render, so the page changes once.

- **List the declared events, not their names.**
  `TransactionRowComponent.confirmed` fails at import if the row does not declare
  it, and a subclass of the row still matches.
- **`rerender_on` hears the event from anywhere on the page.** Any mounted
  component that lists the event re-renders, whether it is the source's parent,
  an ancestor further up, or a sibling such as a summary panel next to the
  rows. All the components one response wakes re-render in a single request.

To run code when a descendant's event arrives, decorate a method with
`Glue.listener`. A listener only hears its descendants: a component stamped in
its template, stamped inside one of those, or returned by one of their
callables, wherever its host mounts it on the page. The component re-renders after it, like after any component
callable; pass `skip_rerender=True` to opt out, though a listener that changes a
retained value re-renders anyway. `required_access=` works as it does on
`Glue.attr`. Take the event to learn which child changed: `event.source` is the
emitting component, rebuilt from its signed token, with its parameters and
scope. Type it with `Glue.ReceivedEvent[...]`:

```python
@Glue.listener(TransactionRowComponent.confirmed)
def row_confirmed(self, event: Glue.ReceivedEvent[TransactionRowComponent]) -> None:
    self.last_confirmed_merchant = event.source.transaction.merchant
```

`event.detail` is the payload the client relayed and is untrusted, like callable
arguments. Read what you need from `event.source` or the database.

A re-render redraws the component's own markup, not the children it stamps: a
child still mounted on the page is kept as it is, with its state. So a child
that shows data another component changes must declare `rerender_on` for the
events that change it, or it shows what it last rendered. See
[keeping children](../components.md#a-parents-re-render-keeps-its-children).

Loading and transport errors remain normal promise behavior: set local loading
state before `await`, catch errors, and clear loading state in `finally`.
