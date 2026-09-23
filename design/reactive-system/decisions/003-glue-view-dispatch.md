# ADR 003: Dispatch Glue Views Through Their Actual Django Route

Status: Accepted; implemented on branch

Date: 2026-09-11

## Context

The current `/__dg__/glue_view/` resolver accepts a target path, resolves it,
and calls the view function directly. View decorators execute, but middleware
sees the Glue endpoint rather than the target path. Path-scoped authentication,
tenant, and permission middleware can therefore be bypassed.

## Decision

`Glue.view(url)` sends a same-origin request to the actual target URL with a
Glue-specific `Accept` media type. The complete normal Django middleware and URL
dispatch path executes. A Glue response middleware packages the rendered body
and introduced addressed objects into the shared HTML envelope.

The media type changes representation only. It grants no authority and requires
no Glue-specific view registration or decorator. The central redispatch
endpoint, synthetic request wrapper, and manual redirect loop are removed.

## Consequences

- Middleware evaluates the real target path and method.
- GET payloads become query parameters; POST payloads remain ordinary
  CSRF-protected JSON requests.
- Redirects use normal HTTP semantics and remain same-origin.
- `Glue.view(url)` retains its arbitrary Django-view ergonomics.
- The Glue response middleware must be ordered so outward middleware operates
  on the final negotiated response. Because that ordering is security-relevant
  and unenforceable by documentation, Glue ships a Django system check that fails
  startup when the middleware is missing or not last in `MIDDLEWARE`.
- **One URL now serves two representations, which obliges `Vary: Accept`.** The
  middleware sets it on every response it negotiates and on every response it
  passes through on a negotiable request. Omitting it lets a shared cache store
  the JSON envelope under the page's cache key — a cache-correctness bug with a
  cache-poisoning failure mode.
- **Only HTML responses are negotiated.** Streaming responses, file downloads,
  existing JSON endpoints, redirects, and non-2xx responses pass through
  untouched; materializing a `StreamingHttpResponse` to read `.content` raises,
  and wrapping a download corrupts it. The client treats a response without the
  envelope marker as a non-fragment outcome.

## Rejected alternatives

- Replay a selected middleware subset inside the Glue endpoint; Django does not
  expose a reliable path-specific subset and global middleware could run twice.
- Require an allowlisted registry of fragment views; this adds ceremony without
  restoring normal request semantics.

The complete transport contract remains in
[`../state-model.md`](../state-model.md#6-effects-and-fragments-are-separate-channels).
