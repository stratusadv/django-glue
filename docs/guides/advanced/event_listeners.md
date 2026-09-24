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

An owner can expose a specific signed child event. For example, a component
with a child model named `entry` whose form declares `saved = Glue.event()`
can declare `saved = Glue.event(from_child='entry.form.saved')`. Consumers then
subscribe with `modal.$on('saved', handler)`. The event keeps the child form as
`event.source` and the owner's proxy as `event.currentTarget`. Other child
events remain private; disposing the owner removes the subscription.

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

Loading and transport errors remain normal promise behavior: set local loading
state before `await`, catch errors, and clear loading state in `finally`.
