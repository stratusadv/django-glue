# ADR 022: Component Callables Re-render Their Component by Default

Status: Accepted; implemented on branch

Date: 2026-09-28

## Context

`component-system.md` §7 states that application code does not invoke `render()`
to reconcile a component after a mutation. It offers one alternative, the client
calling `$refresh()`, and Glue re-renders a component in a callable's own response
only when the callable changed one of its parameters. So after an ordinary action,
one that writes data without moving a parameter, a consumer has two options, and
both are in use:

- **Return `self.render()` from the callable.** Glue's own test fixture does this
  (`test_project/gorilla/components.py`, `drop_first`), and the Profitly prototype
  copied it into every action of its transaction list. It contradicts the spec, and
  it repeats the same line in every action.
- **Fire an event and call `$refresh()` from the client.** The portal's
  time-entry dashboard does this. It follows the spec, but every action costs a
  second request whose only job is to render the component the first request just
  changed.

Comparable frameworks with a server-side component model make re-rendering after
an action the default and skipping it the exception:

| Framework | After an action | To skip the re-render |
|---|---|---|
| Livewire | re-renders the component | `$this->skipRender()` |
| Phoenix LiveView | re-renders what changed in the assigns | assign nothing |
| Blazor | re-renders the component after the event handler | override `ShouldRender()` |
| Django Unicorn | re-renders the component | return a value or opt out |
| Glue today | re-renders only when a parameter changed | nothing to skip |

Glue's transport is closest to Livewire's: it sends the component's rendered HTML
and the client morphs it, rather than sending a server-computed diff as LiveView
and Blazor Server do.

Re-rendering when any retained value changes, a dependency rule in the spirit of
React's, is not sufficient on its own. Most actions change the database, not the
component's declared values, and a component derives what it shows from the
database on every render through `get_context_data()` and its properties. The
Profitly transaction list's only declared value is `month_start`; confirming a
transaction leaves it unchanged, so a rule keyed on declared values would skip the
render that the action most needs.

The portal's component callables were inventoried before this record was drafted:

| Component | Callables | Result | Under an unconditional default |
|---|---|---|---|
| `TimeEntryDashboardComponent` | `current_week`, `previous_week`, `next_week`, `show_week` | none; each moves `week_of` | already re-render today |
| `TimeEntryDashboardComponent` | `bulk_entry_modal` | a modal component | would re-render the dashboard and its seven day children to open a modal |
| `TimeEntryDayComponent` | `new_entry_modal`, `edit_entry_modal`, `delete_entry_modal` | a modal component | would re-render the day to open a modal |
| `TimeEntryDeleteModalComponent` | `delete_entry` | a dict and a `deleted` event | would fail: its render reads the entry the action just deleted |

The form and formset modals and Spire's `FormComponent` and
`ModelFormComponent` declare no component callables; their saves run on child
`ModelGlue`, `FormGlue`, and `FormSetGlue` objects.

## Decision

**A successful callable on a component re-renders that component in the same
response.** The render uses the path that parameter changes already use: a fresh
instance reconstructed from the successor token, so cached properties and
derived values are recomputed from current state rather than read from the
instance that ran the action. The rendered HTML and the introduced child entries
travel in the callable's response, and the client morphs the component's root as
it does for `$refresh()`. Application code does not call `render()`.

**A callable whose declared result is a Glue object does not re-render its
component.** Returning a component or another configured Glue object hands the
interaction to that object, such as a modal the caller mounts. The callable schema
already marks a Glue return, so no declaration is needed.

**`skip_rerender=True` opts a callable out.** It is for callables whose effect leaves
nothing on the component to show, such as one that returns data for the client, or
that remove the component's own subject:

```python
@Glue.attr(required_access=Glue.Access.DELETE, skip_rerender=True)
def delete_entry(self) -> dict:
    result = self.time_entry.services.delete(self.request)
    Glue.event(self, 'deleted', {'date': self.date.isoformat()})
    return result
```

Glue cannot infer that an action removed the row a component represents, so this
case is explicit.

**A callable that changes a retained value still re-renders, whatever it
declares.** If a callable that would otherwise skip the render changes a
parameter or another retained value, the component's markup no longer matches its
state, and Glue re-renders it. This generalizes today's parameters-only rule to
every retained value.

**Only the component whose callable ran re-renders.** Its owner, siblings, and
unrelated components are not re-rendered; they refresh through events and
`$refresh()` as §7 already describes. The children the component stamps are
re-stamped as part of its render and reconciled by key. Glue still infers no
dependency graph from a save.

**A render failure after a successful callable fails the address like any other
error.** A Glue error becomes that address's error entry, which advances nothing,
as `state-model.md` §10 requires of a failed address; any other exception
propagates. The callable's writes have already committed and stand, and the client
keeps its current markup and token. A callable that makes its own render
impossible, such as one deleting the component's subject, declares
`skip_rerender=True`.

**The rule applies to components only.** Models, forms, querysets, formsets, and
functions keep their own refresh semantics; a save on a component's child form
does not re-render the component.

**Specification changes.** `component-system.md` §7, "Refresh is an addressed
Glue-object operation", records that a component callable's response carries the
component's re-render, names the two exceptions and the retained-value guard, and
keeps the rule that application code does not call `render()`.

## Performance

A default re-render is the same work a consumer already pays, in one request
instead of two:

| Pattern | Per action |
|---|---|
| callable, event, client `$refresh()` | two requests, one render |
| callable returning `self.render()` | one request, one render |
| re-render by default | one request, one render |

The remaining costs, and the practice that contains them:

- **Callables that did not need a render.** Returning a Glue object skips it
  automatically; other data-only callables declare `skip_rerender=True`.
- **Large components.** The whole component's HTML is sent and morphed. A
  component whose markup is large splits into smaller components or, for long
  lists, waits on the deferred incremental collection rendering in the roadmap.
  Response compression is expected in production.
- **Child components.** A render re-stamps the component's children, so their cost
  is part of it. Plain lists stay template partials, per §4.
- **High-frequency callables.** A callable bound to keystrokes or dragging renders
  on every call; it is debounced on the client or declares `skip_rerender=True`.
- **Measurement.** Components whose render cost grows with data carry query-count
  and response-size tests.

## Consequences

- An action reconciles its component in one request, and the `self.render()` line
  disappears from consumer code and from Glue's test fixture.
- The portal's week navigation behaves as it does today, and its modal factories
  skip the render without change because they return components. Its
  `delete_entry` declares `skip_rerender=True`. Its events and `$refresh()` calls for
  cross-component updates stay.
- The retained-value guard means an opt-out cannot leave a component's markup
  describing state it no longer has.
- The client needs no new behavior: a callable response carrying component HTML is
  the path parameter changes already take.

## Rejected Alternatives

- **Explicit `return self.render()`.** The spec already rejects it, and it repeats
  one line in every action.
- **Client `$refresh()` after every action.** It follows the spec but costs a
  second request for a render the first request could have included.
- **Re-rendering only when a retained value changes.** Most actions change the
  database, which a component reads on every render but does not declare, so the
  rule would skip the renders that matter. It is kept as the guard on opt-outs.
- **Re-rendering the component's owner as well.** An owner's render is often the
  most expensive on the page, and deciding which ancestors a save affects is the
  dependency inference §7 declines.
- **Server-side diffs of the rendered HTML.** LiveView and Blazor Server send only
  what changed, which reduces payloads for large components. It is a transport
  change independent of this record, and the deferred incremental rendering work
  is where it belongs.
- **Opting in per callable (`rerender=True`).** It makes the common case the one
  that needs a declaration, which is what every compared framework avoids.
