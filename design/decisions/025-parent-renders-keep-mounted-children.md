# ADR 025: A Parent's Re-render Keeps Its Mounted Children

Status: Accepted; implemented on branch

Date: 2026-09-29

Supersedes the re-stamping consequence and the "one frame on screen" skip of
[ADR 024](024-component-listeners.md), and narrows its "events reach
ancestors" rule for `rerender_on`.

## Context

A component's template stamps its children with `{% glue_component %}`. Every
render of the parent runs those tags again, and a tag can only build a child
from its parameters: the request carries the parent's token, not the children's,
and Glue keeps no component state on the server. So a parent re-render re-stamps
every child. Each is introduced and mounted again, gets a new token, and loses
any state it held only in its own token.

ADR 022 made re-rendering the default after a component's callable, and ADR 024
added re-rendering when a descendant emits an event. Together they made the
re-stamp common and expensive:

- **Children lose state.** A counter card that counted clicks returns to its
  mounted value whenever its parent re-renders.
- **A parent re-render costs as much as the whole subtree.** Confirming one row
  of the Profitly transaction review re-renders all of its rows, about 170 KB
  for an 18-row month, although the list only needs its summary redrawn.
- **A child does not own its own lifecycle.** Whether a child is rebuilt
  depends on what its ancestors do, which contradicts component-system.md §7,
  "Glue objects are independent addressed islands".

Livewire faces the same constraint and keeps the child: the parent's snapshot
remembers the children it stamped, and on a later render the child tag emits a
placeholder instead of running the child, so the browser keeps the child's
existing markup. A prop changes a skipped child only when the prop is marked
`#[Reactive]`.

## Decision

### A mounted child is skipped

When a component renders in response to a Glue request, a stamped child that the
client reports as still mounted is not rendered. The tag emits a placeholder,
and the client keeps the child's live element.

1. **The client reports mounted children.** Every request entry for a
   component lists, under `mounted`, the addresses of the component roots
   inside its root. The list is untrusted and needs no signature: a client that
   lists a child it does not have only denies itself that child's markup.
2. **A child's address fingerprints its parameters and access.** A stamped
   child's address is derived from its parent's address, its tag, its key, and
   a short hash of its signed parameters and access. A child whose parent now
   passes different parameters has a different address, is not in `mounted`,
   and is stamped fresh. Parameters are therefore reactive without a marker; a
   parameter change gives the child a new identity and resets its state, as a
   changed `wire:key` does in Livewire.
3. **The tag emits a placeholder for a mounted child.** It constructs the child
   to compute its address and, when that address is in `mounted`, renders
   `<template data-glue-keep="ADDRESS"></template>` instead of introducing,
   mounting, and rendering it. `<template>` is allowed anywhere in HTML,
   including inside a table, so the placeholder is not moved by the parser
   whatever element the child's root is. Duplicate-key checking still runs.
4. **The client restores the child before morphing.** Before morphing a
   response's HTML, the client replaces each placeholder with a copy of the
   live element at that address. The morph then finds that subtree unchanged
   and leaves the child's DOM, Alpine state, and proxy alone. A placeholder
   whose element is gone is dropped.
5. **Page loads are unchanged.** A page, a fragment served by `as_view()` or
   `as_page()`, and an HTML result that is not a component's own render carry
   no `mounted` list, so every child renders.

A component's own render, through its callable, `$refresh()`, or `$receive`,
still renders the component itself. `$refresh()` on a parent no longer
refreshes its children; refresh the child, have it re-render on an event, or
stamp it with `rerender_with_parent`.

### A stamp can re-render with its parent

Some children are plain views of data their parent re-reads, with parameters
that do not change when that data does: a week dashboard's day columns keep
their dates when an entry is saved. The template that stamps such a child says
so with a bare flag:

```django
{% glue_component 'time_tracker/time_entry_day' date=date user_id=component.user_id key=date rerender_with_parent %}
```

- **A flagged stamp always renders in full,** even when the client reports the
  child mounted. The child is introduced and mounted again and its markup comes
  back inside the parent's, at the same address, so the client updates the
  existing child. Its own retained state resets on every parent render, which is
  the cost the flag accepts.
- **The flag is on the stamp, not the child's class.** The same child can be a
  view of its parent in one template and an independent island in another; only
  the stamping template knows which.
- **It is a bare word,** like `only` on `{% include %}`. Parameters are always
  `name=value`, so it cannot collide with one, and an unknown bare word is a
  `TemplateSyntaxError` when the template is parsed.

### Freshness is declared by the child

A skipped child shows what it last rendered. A child whose markup depends on
data another component changes declares the events that make it stale, with the
same `rerender_on` it would use for its own children:

```python
class CloseProgressComponent(SignedInComponent):
    rerender_on = (
        TransactionRowComponent.confirmed,
        TransactionRowComponent.receipt_attached,
    )
```

For that to work between siblings, `rerender_on` is delivered page-wide:

- **`rerender_on` reaches every mounted component that declares the event**,
  not only the source's ancestors. Re-rendering is a read on the receiving
  component's own token, and the detail is already untrusted, so no ancestry
  check is needed. The server still verifies that the source token is genuine,
  issued to this session and user, and that its class declares the event.
- **`Glue.listener` keeps the ancestry check.** A listener can read
  `event.source`, and a parent that reads its child should be able to trust that
  it is its child. A `$receive` for a listener-only event from a non-descendant
  is rejected as before.
- **Static data separates the two.** `static_data.rerender_on` lists the event
  identities a component re-renders on, and `static_data.listeners` lists those
  its listener methods handle.

### Delivery is batched

One response can wake many components, such as every row when a merchant rule
is created. The client sends the `$receive` calls one response produces as a
single request with an entry per component, and hands each entry's result back
to its component, which applies it as it would its own call. Calls that carry
files, or two calls for one address, are never batched together.

### The source morphs itself

The source's own render is no longer contained in its ancestors' renders, so
the source always applies its own morph. It still waits for the `$receive`
calls its events started, so the source and the components that react to it
change on screen together.

## Consequences

- A child keeps its state across its parent's re-renders, and a parent
  re-render sends only the parent's markup and any children that are new or
  whose parameters changed.
- A parent's queries still run: its template still iterates the rows it would
  stamp. The saving is in rendering and response size.
- Freshness is explicit. A child that reads shared data and does not declare
  `rerender_on` for the events that change it shows stale data, and nothing
  reports it. This is the price of skipping, and the guide says so.
- Every component request grows by its `mounted` list, one address per mounted
  descendant.
- `state-model.md` §10 gains the `mounted` entry field and component-system.md
  §4 and §7 describe the skip, the placeholder, and page-wide `rerender_on`.

## Alternatives considered

- **Keep re-stamping.** Simple and always fresh, but children lose state, every
  parent render costs its subtree, and a child's lifecycle depends on its
  ancestors.
- **Record stamped children in the parent's signed token.** The server would
  know which children exist without the client's list. It grows the parent's
  token with every child and re-signs it whenever the set changes, to protect a
  decision that only affects what markup the requesting client receives.
- **A `#[Reactive]`-style marker for parameters.** Livewire needs it because a
  skipped child ignores new props. Fingerprinting parameters into the address
  makes every parameter reactive with no marker, at the cost of a new identity.
- **A placeholder with the child's root tag.** Livewire records each child's tag
  name so the placeholder parses in place. `<template>` parses in place in every
  context, so no tag needs recording.
- **A string option, `rerender='with_parent'`, or a class attribute on the
  child.** A string invites misspelled values that only fail at render time, and
  a class attribute puts the parent's knowledge in the child.
- **Keep `rerender_on` ancestor-only and let parents refresh named children.**
  The parent would have to know which of its children an event affects, which
  moves the child's freshness rule into the parent.
