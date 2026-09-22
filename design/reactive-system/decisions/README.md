# Decision Records

| ADR | Status | Decision |
| --- | --- | --- |
| [`001`](001-bundle-alpine.md) | Accepted; implemented on branch | Bundle and own the Alpine core/morph runtime |
| [`002`](002-state-roles.md) | Accepted; implementation pending | Separate value roles from construction parameters |
| [`003`](003-glue-view-dispatch.md) | Accepted; implementation pending | Dispatch Glue views through their actual Django route |
| [`004`](004-addressed-object-composition.md) | Accepted; implementation pending | Compose addressed objects through explicit children and namespaces |
| [`005`](005-attribute-collection-and-registry.md) | Accepted; implementation in progress | Collect declarations once and let each Glue family contribute definitions directly |
| [`006`](006-extra-attribute-hook-name.md) | Accepted; implementation in progress | Name the family/custom extension hook `get_extra_attributes()` |
| [`007`](007-scoped-extra-attribute-declarations.md) | Accepted; implementation in progress | Declare extra attributes as provider/declaration-map pairs |
| [`008`](008-static-external-attribute-providers.md) | Accepted; implementation in progress | Reuse cached static definitions for explicitly selected external providers |
| [`009`](009-add-access.md) | Accepted; implementation pending | Represent creation with `ADD` in the access cascade |
| [`010`](010-target-derived-required-access.md) | Accepted; implemented on branch | Let `required_access` be a callable resolved against the reconstructed target |
| [`011`](011-collection-owned-item-keys.md) | Accepted; implementation pending | Let each collection own its item-key derivation; no `BaseGlue.key` |
| [`012`](012-formset-is-a-keyed-collection.md) | Accepted; implemented on branch | FormSetGlue is a keyed collection of FormGlue, not a BaseFormSet |

Accepted records preserve why a choice was made. If an outcome changes, add a
record that supersedes the earlier one instead of rewriting its decision.

Concerns raised and deliberately not acted on are recorded in
[`../concerns.md`](../concerns.md) rather than here; an ADR records a decision
that changed the design, while that document records one that did not.
