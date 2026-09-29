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

A component that depends on its children declares what it reacts to with
`Glue.listener`, instead of wiring `$refresh()` into its template:

```python
class TransactionReviewComponent(Glue.Component):
    template = 'banking/component/transaction_review.html'

    @Glue.listener(TransactionRowComponent.confirmed, TransactionRowComponent.merchant_rule_created)
    def row_changed(self) -> None:
        """The month summary and other rows from the merchant depend on the row."""
```

When a row stamped in this component's template emits `confirmed`, the client
calls the listening component with the event, runs `row_changed`, and
re-renders the component. The row's own markup is updated by that render, so the
page changes once.

- **Pass the declared event, not its name.** `TransactionRowComponent.confirmed`
  fails at import if the row does not declare it, and a subclass of the row
  still matches.
- **A listener reaches descendants.** A component stamped in the listener's
  template, stamped inside one of those, or returned by one of their callables
  is a descendant, wherever its host mounts it on the page.
- **Handling an event re-renders the component,** like any component callable.
  Pass `skip_rerender=True` to opt out; a listener that changes a retained value
  re-renders anyway. `required_access=` works as it does on `Glue.attr`.
- **Take the event to learn which child changed.** `event.source` is the
  emitting component, rebuilt from its signed token, with its parameters and
  scope. Type it with `Glue.ReceivedEvent[...]`:

```python
@Glue.listener(TransactionRowComponent.confirmed)
def row_confirmed(self, event: Glue.ReceivedEvent[TransactionRowComponent]) -> None:
    self.last_confirmed_merchant = event.source.transaction.merchant
```

`event.detail` is the payload the client relayed and is untrusted, like callable
arguments. Read what you need from `event.source` or the database.

A listener re-renders its whole template, including the children it stamps.
Each re-stamped child is mounted again from its parameters, so state a child
keeps only in memory, such as a click count, returns to its mounted value.
Keep that state in the database or in the parent.

Loading and transport errors remain normal promise behavior: set local loading
state before `await`, catch errors, and clear loading state in `finally`.
