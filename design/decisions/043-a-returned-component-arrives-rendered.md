# ADR 043: A Returned Component Arrives Rendered

Status: Accepted

Date: 2026-11-17

## Context

ADR 022 lets a callable return a component, such as a modal, and "hand the
interaction to that object". The response introduced the component with its
entry alone, so the client had to call `render()` on it before it could show
anything. Every modal opened in two requests, one after the other: the action,
then the render.

That second request is the kind ADR 022 removed for a component's own actions:
a request whose only job is to render what the first one just produced. It
repeats the work every request does before the render: middleware, the session
and user, the token, and the component's parameters, which the first request
had already loaded.

Every component a callable returns is rendered by its caller straight away.
Showcase's 58 such callables open through `modal_component_open()`, which calls
`renderInnerHtml()`; Spire's `load_item_form` and
`load_item_delete_confirmation` open through
`Spire.modal.dispatchGlueComponent()`, which calls `render()`. Measured on
showcase's customer Edit modal:

| | Requests | Localhost | 50 ms round trip |
|---|---|---|---|
| Render requested separately | 2 | 49 ms | 111 ms |
| Render in the same response | 1 | 35 ms | 57 ms |

## Decision

**A component a callable returns arrives rendered.** The response that
introduces it carries the answer its first `render()` would get, and the client
shows it without a second request.

1. The render is the one a `render()` call runs: a fresh instance reconstructed
   from the component's token processes `render`, as ADR 022's re-render does.
   Its required access and `is_authorized()` apply as they would to that call.
   The entries of the children it renders travel with the response's other
   introduced entries.
2. The answer rides on the component's introduced entry as
   `answers: {render: <addressed entry>}`. The general layer knows it only as
   the answer to a named call: `BaseGlue._result_entries()` builds a returned
   object's entries, and `Component` overrides it to add the render. On the
   client, the record holds the answers, and a call made with no arguments and
   no changes to send takes its answer instead of making a request. The answer
   then goes through the same response path as one that came over the network.
3. An answer is used at most once, and only until the record next changes: any
   other call's response, a reintroduction or disposal drops it, and the call is
   then a request. A call with arguments, or with changes to send, is always a
   request.
4. A render Glue refuses, such as one `is_authorized()` denies, is not carried.
   The client's `render()` then makes the request and is refused as before. Any
   other exception the render raises fails the call that returned the
   component, as a template error in a render does.
5. **`defer_render=True` on the component's constructor opts out**:
   `return EntryModal(entry=entry, defer_render=True)`. The component is
   introduced with its entry alone and rendered when the client asks. The flag
   is not signed: only the response that introduces the component reads it. The
   template tag and `as_view()` render their component themselves, so each
   refuses `defer_render` with `GlueComponentParameterError`; `as_view()`
   refuses it when it is called, so a URLconf fails as it loads.

The rule applies to a component a call introduces. A callable that returns one
of its owner's existing children introduces nothing, so nothing is rendered.

## Consequences

- Opening a modal costs one request instead of two, saving a round trip and a
  request's fixed work on every open.
- A response that returns a component carries its HTML. The bytes are the same
  ones the `render()` request used to download.
- A caller that never renders the component it gets back pays for a render it
  does not use. None exists; one would construct the component with
  `defer_render=True`.
- `defer_render` is a constructor keyword, beside `name` and `access`: a
  parameter declared with any of those names would never reach the component.

## Rejected Alternatives

- **An option on `Glue.attr`, such as `skip_result_render=True`.** `Glue.attr`
  declares every kind of callable on every kind of Glue object, and the option
  would mean something only on a component's callable that returns a component.
  The code that builds the component knows whether it will be shown, so the
  choice is made there.
- **A flag the client sends with the call, asking for the result rendered.**
  Every call site would have to pass it, and `modal_component_open()` and
  `dispatchGlueComponent()` receive the call already sent.
- **Rendering the instance the callable returned, without reconstructing it.**
  It saves a reconstruction, but the render would differ from a `render()`
  call's: derived values computed while the callable ran would be reused, which
  ADR 022 reconstructs to avoid.
