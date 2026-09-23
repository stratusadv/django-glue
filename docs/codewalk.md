# Codewalk

Start with `django_glue/shortcuts/glue.py` for registration. A shortcut
configures a `BaseGlue` family and puts the resulting root in
`glue/context.py`. The component tag constructs components at their render
site instead of adding a named global root.

`glue/attributes/collector.py` compiles class declarations and family
attributes into one interface. `glue/base.py` applies the shared admission,
hydration, derivation, authorization, and call pipeline. The family modules
under `glue/objects/django/` own Django-specific fields, queries, forms, and
relation projection.

`glue/policy.py` signs each object's address, capability, reconstruction
parameters, retained state, and child mapping. `resolver/attribute_call/`
validates the flat `objects` request envelope and processes each address.
`response.py` serializes addressed entries, results, and effects.

In the browser, `client_js/src/client.js` installs named roots and dispatches
responses. `client_js/src/runtime/addressRegistry.js` owns one live proxy per
address; the neighboring runtime modules materialize attributes, bind child
paths, and reconcile state. The `proxies/` modules add family behavior.
`client_js/src/htmlRenderer.js` morphs returned HTML after introduced objects
are registered.

Read [Architecture](architecture.md) for the wire and lifecycle overview.
