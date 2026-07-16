# GlueObject Refactor

## Goal

Move Django Glue from proxy-specific serialization paths toward a generic `GlueObject` / `GlueAttribute` system.

The current proxy pipeline has several responsibilities mixed together:

- Proxy policies describe identity, permissions, target reconstruction, and some frontend metadata.
- State classes serialize values differently for models, forms, querysets, templates, and functions.
- Field metadata is mixed into policy data even when it is only useful to the frontend.
- Django models, forms, and querysets are heavily special-cased.

The refactor should make one shared pipeline:

```text
Python target
-> GlueObject
-> GluePolicy + GlueState + GlueMetadata
-> frontend proxy
-> GlueAttributeRequest
-> server resolves policy, applies state, calls attribute
-> returns updated policy/state/metadata/result
```

The larger direction is to make Glue a general Python object proxying system, with Django model, form, queryset, and field support provided by concrete `GlueObject` and `GlueAttribute` classes.

Backend proxy classes are legacy infrastructure in this direction. They should not be the core abstraction for new work and should not be forced into the new model. Existing public frontend proxy ergonomics may remain, but backend serialization, identity, metadata, and attribute request handling should move to `GlueObject`s over time.

## Core Concepts

### GlueObject

`GlueObject` is the runtime backend object that Glue can expose.

Examples:

- `DjangoModelGlueObject`
- `DjangoFormGlueObject`
- `DjangoQuerySetGlueObject`
- `PythonFunctionGlueObject`

Primary responsibilities:

- Build a `GluePolicy`.
- Build `GlueState`.
- Build `GlueMetadata`.
- Resolve a target object from a submitted policy.
- Apply submitted state safely.
- Execute a requested callable attribute.

### GlueAttribute

`GlueAttribute` is the common internal representation for anything exposed by a `GlueObject`.

Examples:

- `DeclaredGlueAttribute`
- `DjangoModelFieldGlueAttribute`
- `DjangoFormFieldGlueAttribute`

Primary responsibilities:

- Describe readable, writable, callable, or relation behavior.
- Provide value serialization and deserialization behavior.
- Provide frontend metadata for that attribute.

Attributes can come from different sources, but should become the same internal shape once adapted:

```text
Glue.Attribute declaration
Django model field
Django form field
custom descriptor/property
```

### GluePolicy

`GluePolicy` is the signed, client-held lifecycle object for a glued backend object.

It replaces the current role of `ProxyPolicy`.

It answers:

- What backend thing is this frontend proxy bound to?
- How can the server reconstruct it?
- What attributes are allowed?
- Which session is it bound to?
- Has the client tampered with it?

Expected contents:

- Proxy name.
- Adapter namespace or object namespace.
- Target reference.
- Session binding.
- Access level.
- Allowed attributes.
- Expiry and signature.

Only the policy is authoritative. The server must validate its signature, session binding, expiry, and allowed attribute surface on every attribute request.

### GlueState

`GlueState` contains mutable values and runtime data for a glued object.

Examples:

- `instance_data`
- form errors
- queryset `list_data`
- selected model instance data
- other runtime values

The client may submit state, but the server must treat it as untrusted input. It is only valid after being checked against the signed `GluePolicy` and validated by the relevant adapter.

### GlueMetadata

`GlueMetadata` contains frontend construction and display hints.

Examples:

- field types
- labels
- help text
- widgets
- choices metadata
- choices cache keys
- date parsing hints
- primary key field name

Metadata is not authoritative. The frontend may use it to construct proxy fields, inputs, and display helpers, but the server must not trust submitted metadata for permissions, allowed fields, or validation.

### GlueAttributeRequest

`GlueAttributeRequest` is the server request shape for calling an exposed callable attribute.

There is no separate operation object. Non-callable attributes are read and written through state on the frontend. Server requests call named callable attributes and submit the current state alongside the request.

Examples:

```json
{
  "policy": {...},
  "state": {...},
  "attribute": "save",
  "kwargs": {}
}
```

The whole HTTP request may contain a policy, state, files, an attribute name, and kwargs. The attribute name tells Glue which callable policy attribute to invoke.

## Payload Shape

Initial page render:

```json
{
  "gorilla": {
    "policy": {
      "name": "gorilla",
      "namespace": "django_model",
      "target": {
        "model_class": "test_project.gorilla.models.Gorilla",
        "pk": 12
      },
      "access": "change",
      "attributes": {
        "id": {"access": "view", "readable": true, "writable": false},
        "name": {"access": "change", "readable": true, "writable": true},
        "created_at": {"access": "view", "readable": true, "writable": false},
        "save": {"access": "change", "callable": true}
      },
      "session_id": "...",
      "signature": "..."
    },
    "state": {
      "instance_data": {
        "id": 12,
        "name": "Koko",
        "created_at": "..."
      },
      "errors": {}
    },
    "metadata": {
      "fields": {
        "name": {
          "type": "CharField",
          "label": "Name",
          "max_length": 255
        },
        "created_at": {
          "type": "DateTimeField",
          "label": "Created at",
          "editable": false
        }
      }
    }
  }
}
```

Attribute request:

```json
{
  "policy": {...},
  "state": {...},
  "attribute": "save",
  "kwargs": {}
}
```

Attribute response:

```json
{
  "policy": {...},
  "state": {...},
  "metadata": {...},
  "result": {...},
  "messages": []
}
```

Responses should usually return updated state. They only need to return updated metadata when the frontend construction hints changed.

## Server Lifecycle

### Registration

```text
Glue.model(request, "gorilla", gorilla)
-> creates DjangoModelGlueObject
-> glue object builds policy/state/metadata
-> policy is signed
-> payload is stored for template initialization
```

### Attribute Request Handling

```text
frontend sends policy + state + attribute + kwargs
-> server verifies policy signature/session/expiry
-> registry finds GlueObject class by policy.namespace
-> GlueObject resolves instance/queryset/form from policy identity
-> GlueObject validates and applies submitted state
-> GlueObject calls attribute
-> server returns updated policy/state/metadata/result
```

## Adapter Responsibilities

### DjangoModelGlueObject

Represents Django model instances.

Responsibilities:

- Convert a model instance into a policy target reference.
- Use Django model metadata to discover fields.
- Convert model fields into `DjangoModelFieldGlueAttribute` instances.
- Serialize model values into `GlueState`.
- Build field metadata into `GlueMetadata`.
- Validate and apply submitted state through Django `ModelForm` behavior.
- Resolve a model instance from the submitted policy.

It should also expose model-level callable attributes such as:

- `save`
- `delete`
- custom `Glue.Attribute` declarations on the model

### DjangoModelFieldGlueAttribute

Represents individual Django model fields.

Responsibilities:

- Determine whether the field is readable.
- Determine whether the field is writable.
- Determine required access.
- Provide serialization and deserialization behavior.
- Provide frontend metadata.

Examples:

```text
CharField
  -> string value, max_length metadata

DateTimeField
  -> datetime serializer, date metadata

ForeignKey
  -> relation serializer, related model metadata

ManyToManyField
  -> relation list serializer

ImageField/FileField
  -> browser-friendly file metadata serializer
```

### DjangoFormGlueObject

Represents Django forms and model forms.

Responsibilities:

- Convert form fields into glued attributes.
- Serialize form initial/data/errors into state.
- Build form field metadata.
- Resolve form classes from policies.
- Bind submitted state back to a form.
- Expose `validate` and `save` callable attributes where available.

### DjangoFormFieldGlueAttribute

Represents individual Django form fields.

Responsibilities are similar to `DjangoModelFieldGlueAttribute`, but based on `forms.Field` objects instead of `models.Field` objects.

It should support:

- regular form fields
- choice fields
- model choice fields
- model multiple choice fields
- file fields
- date and datetime fields

### DjangoQuerySetGlueObject

Represents Django querysets.

Responsibilities:

- Convert a queryset into a policy target reference.
- Serialize list data into state.
- Build row metadata, probably by delegating to `DjangoModelGlueObject`.
- Expose queryset callable attributes such as:
  - `query_with_params`
  - `new`
  - refresh/reload behavior
- Build child model policies/states for queryset rows.

## Design Rules

### The policy Is Authoritative

The server must only trust `GluePolicy`.

The policy must be signed and should include:

- target reference
- session binding
- access level
- allowed attribute surface
- expiry or max age

### State Is Input

`GlueState` is mutable client data. It may be useful, but it is never trusted by itself.

Submitted state must be checked against the policy and validated through the relevant adapter.

### Metadata Is Frontend-Only

`GlueMetadata` exists to help the frontend construct useful proxy objects and UI helpers.

The server must not trust metadata submitted by the client.

### Avoid A Recursive Tree As The Core Model

Django object graphs are not trees. Models can share references, contain cycles, and appear in multiple contexts.

The core model should use stable policies and registries. Nested values may serialize as embedded data or references to other glued objects, but Glue should not assume a tree-shaped object graph.

### Adapters Should Produce A Common Shape

After discovery, Glue should not care whether an attribute came from:

- a user-declared `Glue.Attribute`
- a Django model field
- a Django form field
- a custom descriptor

Each should become a common internal glued attribute representation.

## Migration From Current Code

Current code maps roughly as follows:

```text
ProxyPolicy
-> GluePolicy

ProxyPolicySubjectDetails
-> policy.target + policy.namespace

bound_attributes
-> policy.attributes

included_fields rich metadata
-> split between policy.attributes and GlueMetadata.fields

proxy-specific state classes
-> GlueState

action/event resolver
-> GlueAttributeRequest resolver

proxy-specific serialization
-> GlueObject + GlueAttribute
```

## Suggested Migration Path

1. Introduce `GluePolicy`, `GlueState`, `GlueMetadata`, and `GlueAttributeRequest` alongside current classes.
2. Introduce the object resolver registry.
3. Implement standalone `DjangoModelFieldGlueAttribute`, `DjangoFormFieldGlueAttribute`, `DjangoModelGlueObject`, `DjangoFormGlueObject`, and `DjangoQuerySetGlueObject`.
4. Implement standalone template and function glue objects.
5. Build adapter-driven registration and attribute request endpoints separately from backend proxy classes.
6. Migrate `Glue.model`, `Glue.form`, `Glue.queryset`, `Glue.template`, and `Glue.function` to adapter-driven registration.
7. Replace current action/event request parsing with `GlueAttributeRequest`.
8. Deprecate and remove redundant backend proxy classes after adapter-driven behavior reaches parity.

This migration should preserve current public APIs while changing the internal pipeline.
