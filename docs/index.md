# Django Glue

Django Glue connects Django models, forms, querysets, functions, and rendered
components to a reactive Alpine.js client. A Django view registers Glue objects;
the page receives one client proxy for each live address. Calls return
authoritative state and any newly introduced objects.

## Start here

1. [Install Django Glue](getting_started/installation.md).
2. [Register and use your first model](guides/quick_start.md).
3. Read the [core concepts](guides/introduction.md) before adding relations,
   components, or custom objects.

## What it provides

- Model and form fields with editable drafts, validation errors, and typed
  field descriptions.
- Querysets with server-side filtering, ordering, and pagination. Rows are
  independently addressed model proxies.
- Django template components with declared parameters, server-rendered HTML,
  Alpine morphing, and declared events.
- Access levels `VIEW`, `ADD`, `CHANGE`, and `DELETE`, checked by the server
  when objects are introduced and called.
- `Glue.view(url)` for HTML from an ordinary Django route, including objects
  introduced by that render.

The client includes Alpine.js and its morph plugin. Every introduced object
arrives with a complete first snapshot; queryset rows arrive when queried.

The [architecture guide](architecture.md) explains the signed policy token,
address registry, request envelope, and object lifecycle.
