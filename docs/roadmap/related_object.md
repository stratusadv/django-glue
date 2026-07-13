# Related Object Handling

This document captures the proposed direction for related object management in
Django Glue model proxies.

## Current Behavior

Current model proxy behavior is mostly form-shaped rather than object-shaped.
Scalar model fields are serialized into `instance_data` and exposed directly on
the frontend. Forward foreign keys are serialized as raw primary key values.
Direct many-to-many fields can be serialized as lists of related summaries such
as `{pk, __str__}`. Reverse relations, such as `parent.children` or
`gorilla.fights_as_red_corner`, are not currently included because they are not
concrete model fields and are not returned by `model_to_dict()`.

This creates an inconsistent frontend model:

```javascript
child.parent                 // raw FK value
gorilla.skills               // selected related summaries
gorilla.fights_as_red_corner // undefined
```

The long-term direction should separate object navigation from form editing.

## Proposed Frontend Semantics

Direct model properties should feel like Django model attributes:

```javascript
model.scalar_field          // scalar value
model.parent                // related model object/proxy
model.parent_id             // raw FK id
model.skills                // related queryset/collection proxy
model.skills_pks            // raw related PK list
model.children              // reverse relation queryset/collection proxy
model.children_pks          // raw related PK list
```

The `$fields` API should remain the form/editing contract:

```javascript
model.$fields.name.value    // editable scalar value
model.$fields.parent.value  // FK pk
model.$fields.skills.value  // M2M pk list
model.$fields.parent.choices
model.$fields.skills.choices
```

The guiding rule is:

> Direct model properties represent object access. `$fields` represents form
> state, validation, and editing metadata.

## Raw Identity Fields

For forward foreign keys and one-to-one fields, use Django's native raw-id
convention where possible:

```javascript
child.parent
child.parent_id
```

For plural relations, use a consistent PK-list convention:

```javascript
gorilla.skills
gorilla.skills_pks

gorilla.fights_as_red_corner
gorilla.fights_as_red_corner_pks
```

Plural relation properties should be queryset proxies, whether they are direct
many-to-many fields or reverse foreign-key relations. The raw PK list remains
available separately for form state and lightweight identity tracking.

## Lazy Loading

To preserve lazy-loading benefits, `$fields` should store raw identity values
rather than full related objects.

For many-to-many fields:

```javascript
gorilla.skills               // lazy collection proxy
gorilla.skills_pks           // [1, 2, 3]
gorilla.$fields.skills.value // [1, 2, 3]
```

For foreign keys:

```javascript
child.parent                 // related model proxy
child.parent_id              // 12
child.$fields.parent.value   // 12
```

This avoids duplicating relationship payloads while keeping save-oriented state
small and explicit.

## Preloading From Django ORM State

Relation preloading should follow Django ORM loading state rather than requiring
Glue-specific configuration for common cases.

Forward foreign-key and one-to-one preload detection:

```python
field = instance._meta.get_field('parent')
field.is_cached(instance)
```

This is true when the object came from:

```python
Child.objects.select_related('parent')
```

Reverse foreign-key and many-to-many preload detection:

```python
relation_name in getattr(instance, '_prefetched_objects_cache', {})
```

This is true when the object came from:

```python
Parent.objects.prefetch_related('children')
Gorilla.objects.prefetch_related('skills')
```

The proposed rule is:

> Glue serializes related objects that Django has already selected or
> prefetched.

This lets consumers control payload size using familiar ORM tools:

```python
child = Child.objects.select_related('parent').get(...)
parent = Parent.objects.prefetch_related('children').get(...)
gorilla = Gorilla.objects.prefetch_related('skills').get(...)
```

## Annotated And Extra Instance Values

Annotated fields are related to serialization but should remain read-only
frontend data. Queryset proxies already include annotations because
`GlueQuerySetProxy` adds `queryset.query.annotations` to the `.values(...)`
output. Single model proxies do not intentionally include annotations today
because `model_to_dict()` only includes real model/form fields.

A safe way to include annotations on a single model instance is to serialize
public, instance-only values already present in `instance.__dict__`, while
excluding real model fields and class attributes. This avoids accidentally
touching descriptors, managers, services, properties, or methods.

Conceptual helper:

```python
def extra_instance_data(instance):
    instance_keys = set(instance.__dict__)
    class_keys = set(vars(instance.__class__))

    field_keys = {
        field.name for field in instance._meta.concrete_fields
    } | {
        field.attname for field in instance._meta.concrete_fields
    } | {
        field.name for field in instance._meta.many_to_many
    }

    extra_keys = instance_keys - class_keys - field_keys - {'_state'}

    return {
        key: instance.__dict__[key]
        for key in extra_keys
        if not key.startswith('_')
    }
```

This includes queryset annotations materialized on the instance while avoiding
attributes like `objects` and descriptor-backed services.

## Implementation Phases

### Phase 1: Extra Instance Serialization

- Add annotation and extra-instance serialization for single model proxies.
- Keep direct relation behavior mostly unchanged.
- Ensure extra values are read-only frontend data and are not submitted into
  form saves.

### Phase 2: Relation Classification

- Add Python-side relation metadata classification.
- Distinguish scalar fields, forward FK/one-to-one, direct many-to-many, and
  reverse relations.
- Emit raw identity fields such as `parent_id`, `skills_pks`, and
  `children_pks`.

### Phase 3: Preloaded Relation Proxies

- Create nested model proxy seeds for loaded FK/one-to-one relations.
- Create queryset proxy seeds for loaded M2M and reverse relations.
- Define direct frontend relationship properties as model/queryset proxies
  instead of raw form values.

### Phase 4: Lazy Relation Proxies

- Add lazy-loading relation proxies for relations that were not preloaded.
- Support APIs such as:

```javascript
await child.parent.load()
await parent.children.all()
```

## Core Architectural Decision

Django Glue should move from "model proxy as form state" toward "model proxy as
object graph access", while keeping `$fields` as the explicit editing layer.
This gives the library a clearer long-term foundation:

- Direct properties are domain/object access.
- `$fields` is edit/form state.
- Scalar fields stay scalar.
- Singular relations become model proxies.
- Plural relations become queryset proxies.
- Raw relationship identity is exposed with explicit `*_id` and `*_pks`
  properties.
