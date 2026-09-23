# Architecture

The repository's `design/reactive-system/state-model.md` and
`design/reactive-system/component-system.md` are the authoritative contracts.
This page maps those contracts to the implementation.

## Registration and page load

`Glue.model()`, `Glue.queryset()`, `Glue.form()`, `Glue.formset()`, and
`Glue.function()` configure server objects. `Glue.object()` registers a custom
`BaseGlue`. Each belongs to the request's `GlueContextManager`.
`{% glue_component %}` constructs and renders a registered `Component` at a
template site. `{% django_glue_init %}` emits named page objects as a flat
`objects` list; a stamped component root carries its own subtree entries.

Each entry has an opaque address and signed policy token, plus unsigned
`static_data` and `computed_data`. `static_data` describes the interface;
`computed_data` contains current derived output. A token carries
reconstruction parameters, server-retained state, capability, and shallow
child addresses. Ordinary values never contain a Glue object recursively.

## Addressed requests

The browser owns one live proxy per address in `client_js/src/runtime/`.
The attribute materializer attaches value and callable paths; the child
binder resolves addressed children. Proxies expose family-specific behavior
such as queryset chaining or model saving.

An attribute request posts an `objects` array to
`/__dg__/callable_attribute/`. Each requested entry contains its address,
policy token, editable `updates`, and optional `call`. The server verifies
the token, reconstructs and authorizes the object, admits updates, performs
the call, and returns addressed response entries. An entry may fail without
advancing other entries in the batch. Malformed envelopes fail as a whole.

The client registers introduced entries before resolving results, reconciles
server state with edits made while the request was in flight, binds children,
morphs HTML when present, then applies disposal and other effects. Unchanged
tokens and computed output may be omitted; the client retains its last value.

## Identity and lifecycle

A child has its own policy and editable draft. A parent signs only its child
path to address mapping. Queryset rows, formset forms, sequence items, and
components are keyed children; callable results may be transient children.
Removing a child disposes its proxy and descendants. A held reference becomes
a tombstone that rejects later calls. A later introduction at the same address
creates a new proxy generation; responses from the old generation are ignored.

## Django integration

`Glue.view(url)` requests the actual Django URL with Glue content negotiation.
`GlueViewMiddleware` packages the rendered HTML and objects introduced
by the view. The target route's normal middleware and view authorization run.
`GlueTemplateResponse` and HTML attributes use the same rendering path.

## Security boundary

The signed policy is a capability, not a client-editable state object. The
server intersects current declarations, signed permission, and current
application authorization. `VIEW < ADD < CHANGE < DELETE` separates creation
from edits to persisted objects. Query continuations are signed and bounded
before deserialization; the internal unpickler admits only approved classes.
CSRF protection applies to requests. The policy lifetime is 24 hours from
issuance by default.

## Code map

| Concern | Main code |
| --- | --- |
| Server object and declaration pipeline | `django_glue/glue/base.py`, `django_glue/glue/attributes/` |
| Policies and addressed children | `django_glue/glue/policy.py`, `django_glue/glue/children.py` |
| Django families | `django_glue/glue/objects/django/` |
| Components and template tag | `django_glue/glue/component.py`, `django_glue/templatetags/django_glue.py` |
| Client registry and reconciliation | `client_js/src/runtime/` |
| Client family proxies | `client_js/src/proxies/` |
| HTML rendering and view transport | `client_js/src/htmlRenderer.js`, `django_glue/middleware.py` |
