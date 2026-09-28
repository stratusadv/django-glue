# Decision Records

| ADR | Status | Decision |
| --- | --- | --- |
| [`001`](001-bundle-alpine.md) | Accepted; implemented on branch | Bundle and own the Alpine core/morph runtime |
| [`002`](002-state-roles.md) | Accepted; implemented on branch | Separate value roles from construction parameters |
| [`003`](003-glue-view-dispatch.md) | Accepted; implemented on branch | Dispatch Glue views through their actual Django route |
| [`004`](004-addressed-object-composition.md) | Accepted; implemented on branch | Compose addressed objects through explicit children and namespaces |
| [`005`](005-attribute-collection-and-registry.md) | Accepted; implemented on branch | Collect declarations once and let each Glue family contribute definitions directly |
| [`006`](006-extra-attribute-hook-name.md) | Accepted; implemented on branch | Name the family/custom extension hook `get_extra_attributes()` |
| [`007`](007-scoped-extra-attribute-declarations.md) | Accepted; implemented on branch | Declare extra attributes as provider/declaration-map pairs |
| [`008`](008-static-external-attribute-providers.md) | Accepted; implemented on branch | Reuse cached static definitions for explicitly selected external providers |
| [`009`](009-add-access.md) | Accepted; implemented on branch | Represent creation with `ADD` in the access cascade |
| [`010`](010-target-derived-required-access.md) | Accepted; implemented on branch | Let `required_access` be a callable resolved against the reconstructed target |
| [`011`](011-collection-owned-item-keys.md) | Accepted; implemented on branch | Let each collection own its item-key derivation; no `BaseGlue.key` |
| [`012`](012-formset-is-a-keyed-collection.md) | Accepted; implemented on branch | FormSetGlue is a keyed collection of FormGlue, not a BaseFormSet |
| [`013`](013-policy-token-lifetime.md) | Accepted; implemented on branch | The policy-token lifetime is 24 hours from issuance |
| [`014`](014-lazy-snake-case-component-discovery.md) | Accepted; implemented on branch | Lazy snake_case component discovery by name |
| [`015`](015-signed-queryset-query-permissions.md) | Accepted; implemented on branch | Queryset query permissions are signed full paths and lookups, derived from exposure by default |
| [`016`](016-field-metadata-never-shadows-field-members.md) | Accepted; implemented on branch | Server field metadata never shadows a member the field class defines |
| [`017`](017-signed-queryset-seek-keys.md) | Accepted; implemented on branch | Queryset seek keys are signed continuation data bound to their queryset and query |
| [`018`](018-required-save-access.md) | Accepted; implemented on branch | `Glue.Access.required_save_access` is the one target-derived rule for the access a save or validation requires |
| [`019`](019-address-references-do-not-own.md) | Accepted; implemented on branch | Ownership follows address derivation; a reference never owns or disposes, and relation children reintroduce through their collection |
| [`020`](020-new-draft-forms-use-admitted-initial.md) | Accepted; implemented on branch | Build new draft forms from admitted initial state before binding children |

Accepted records preserve why a choice was made. If an outcome changes, add a
record that supersedes the earlier one instead of rewriting its decision.

Concerns raised and deliberately not acted on are recorded in
[`../concerns.md`](../concerns.md) rather than here; an ADR records a decision
that changed the design, while that document records one that did not.
