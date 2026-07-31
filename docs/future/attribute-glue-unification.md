# Future: Attribute and GlueObject Unification

## Current State

The codebase has two parallel hierarchies:

- **`BaseGlue`** - Wraps domain objects (model, form, queryset, function, template)
- **`BaseGlueAttribute`** - Represents access points on a GlueObject (fields, methods, nested objects)

These share significant structural overlap:

| Concept        | BaseGlue                   | BaseGlueAttribute                   |
| -------------- | -------------------------- | ----------------------------------- |
| `name`       | ✓                         | ✓                                  |
| `access`     | ✓                         | ✓ (`required_access`)            |
| `namespace`  | ✓ (class-level)           | ✓ (in metadata)                    |
| `owner`      | N/A (top-level)            | ✓                                  |
| `identity`   | ✓                         | ✗ (uses`owner.identity`)         |
| `state`      | ✓ (aggregates attributes) | ✓ (some subclasses)                |
| `metadata`   | ✓                         | ✓                                  |
| `policy`     | ✓ (generates own)         | ✗ (name appears in owner's policy) |
| `attributes` | ✓ (has children)          | ✗ (is a leaf... mostly)            |

## Key Insight

**An attribute is essentially a GlueObject that doesn't handle its own policy generation.**

Attributes are child GlueObjects that:

1. Don't have their own identity (derived from parent + name)
2. Don't generate standalone policies (included in parent's policy)
3. May or may not have children of their own

## Current Attribute Class Issues

The attribute hierarchy has some inconsistencies:

- `StateAttribute.state` returns `{}` - never useful directly
- `ReadableAttribute` has state but doesn't inherit from `StateAttribute`
- `ContainerAttribute` says "non-state" but containers might want state
- `StateAttribute` docstring mentions "nested Glue attributes" which sounds like `ContainerAttribute`

## Proposed Unification

Add optional `owner` to `BaseGlue` and change policy generation to be compositional:

```python
class BaseGlue:
    def __init__(self, *, name: str, access: GlueAccess, owner: BaseGlue | None = None):
        self.name = name
        self.access = access
        self.owner = owner

    @property
    def policy_fragment(self) -> dict:
        """The bones: identity, access, attributes, namespace."""
        return {
            'name': self.qualified_name,
            'namespace': self.namespace,
            'access': self.access,
            'identity': self.identity,
            'attributes': [child.policy_fragment for child in self.children],
        }

    @property
    def policy(self) -> GluePolicy:
        if self.owner is not None:
            raise RuntimeError("Child GlueObjects don't generate their own policy")
        return GluePolicy.from_fragment(self.policy_fragment, request=self.request)
```

Then:

- `ModelGlue`, `FormGlue`, `QuerySetGlue` - root GlueObjects with their own policies
- `ModelFieldAttribute` → becomes `FieldGlue` (leaf with state)
- `CallableAttribute` → becomes `CallableGlue` (invocable, no state)
- `ContainerAttribute` → becomes `ContainerGlue` with actual child GlueObjects
- `GlueObjectAttribute` → the nested GlueObject directly (no wrapper needed)

## Pros

- **Single unified concept** - easier to understand
- **Explicit composition** - a ModelGlue *contains* FieldGlue children
- **Natural nesting** - ContainerGlue has children (no more flat qualified names)
- **Clean policy generation** - recursive composition
- **Frontend/backend symmetry** - proxy structure mirrors backend structure

## Cons / Concerns

1. **Reconstruction complexity**: Root reconstructs itself, children derived from underlying object. Should work similarly to current approach.
2. **Identity for leaf nodes**: Fields don't need identity - it's implicit from parent's identity + field name. Would need to handle this case.
3. **Overhead**: Every field becomes a full GlueObject. Probably negligible but worth measuring.
4. **`@DeclaredAttribute` decorator**: Would return a `CallableGlue` descriptor. Could actually be cleaner.
5. **State flow**: Currently `BaseGlue.state` aggregates `attribute.state`. Would become `child.state`. Same pattern.

## Migration Path

Could be done incrementally:

1. Make `BaseGlueAttribute` inherit from `BaseGlue`
2. Add `owner` parameter to `BaseGlue.__init__`
3. Migrate attribute subclasses one by one
4. Update policy generation to be compositional
5. Clean up redundant code

## Files Affected

- `glue/base.py` - add owner, change policy generation
- `glue/attributes/*.py` - become GlueObject subclasses
- `glue/attributes/collector.py` - collect child GlueObjects instead of attributes
- `glue/policy.py` - handle nested fragments vs flat names
- Frontend - minimal changes if wire format stays the same

## Decision

**Deferred.** This is a significant architectural change. Capturing for future consideration when:

- The current attribute confusion causes real bugs
- A major version bump is planned
- There's bandwidth for careful refactoring with full test coverage
