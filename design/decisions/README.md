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
| [`012`](012-formset-is-a-keyed-collection.md) | Accepted; implemented on branch; partly superseded by 028 | FormSetGlue is a keyed collection of FormGlue, not a BaseFormSet |
| [`013`](013-policy-token-lifetime.md) | Accepted; implemented on branch | The policy-token lifetime is 24 hours from issuance |
| [`014`](014-lazy-snake-case-component-discovery.md) | Accepted; implemented on branch; partly superseded by 027 | Lazy snake_case component discovery by name |
| [`015`](015-signed-queryset-query-permissions.md) | Accepted; implemented on branch | Queryset query permissions are signed full paths and lookups, derived from exposure by default |
| [`016`](016-field-metadata-never-shadows-field-members.md) | Accepted; implemented on branch | Server field metadata never shadows a member the field class defines |
| [`017`](017-signed-queryset-seek-keys.md) | Accepted; implemented on branch | Queryset seek keys are signed continuation data bound to their queryset and query |
| [`018`](018-required-save-access.md) | Accepted; implemented on branch | `Glue.Access.required_save_access` is the one target-derived rule for the access a save or validation requires |
| [`019`](019-address-references-do-not-own.md) | Accepted; implemented on branch | Ownership follows address derivation; a reference never owns or disposes, and relation children reintroduce through their collection |
| [`020`](020-new-draft-forms-use-admitted-initial.md) | Accepted; implemented on branch | Build new draft forms from admitted initial state before binding children |
| [`021`](021-component-parameter-initializers.md) | Accepted; implemented on branch; extended by 026 and 029 | A component parameter may be a model, initialized from its signed key by a decorated method, or a dataclass encoded through the serializer registry |
| [`022`](022-component-callables-re-render-by-default.md) | Accepted; implemented on branch | A successful component callable re-renders its component in the same response, unless it returns a Glue object or declares `skip_rerender=True` |
| [`023`](023-component-as-page.md) | Accepted; implemented on branch | A view serves a component it constructed with `component.as_page(request)`; `get_view_kwargs` is deprecated |
| [`024`](024-component-listeners.md) | Accepted; implemented on branch; partly superseded by 025 | A component declares the events it re-renders on with `rerender_on` and runs code for a descendant's events with `Glue.listener`; the client delivers them in a follow-up `$receive` call |
| [`025`](025-parent-renders-keep-mounted-children.md) | Accepted; implemented on branch | A parent's re-render keeps the children the client reports mounted; a child declares its own freshness with `rerender_on`, delivered page-wide and batched |
| [`026`](026-bounded-model-parameters.md) | Accepted; implemented on branch | A model parameter whose initializer takes `(self, model, pk)` accepts a row of any concrete subclass of its return annotation, signing the model's label with the key |
| [`027`](027-component-lookup-like-templates.md) | Accepted; implemented on branch | Component lookup is configured by `DJANGO_GLUE_COMPONENTS`, shaped like `TEMPLATES`: `DIRS` searched in order, then installed apps, first location defining the class wins |
| [`028`](028-formsets-edit-saved-records.md) | Accepted; implemented on branch | A formset may be seeded with saved records; removing a saved row signs a pending deletion that `save` applies, with `save_forms` and `delete_removed` as hooks |
| [`029`](029-draft-model-parameters.md) | Accepted; implemented on branch | A model parameter whose initializer's key annotation admits `None` may be left out for a row that does not exist yet; the initializer builds it, and a saved draft is signed by its new key |

Accepted records preserve why a choice was made. If an outcome changes, add a
record that supersedes the earlier one instead of rewriting its decision.

Concerns raised and deliberately not acted on are recorded in
[`../concerns.md`](../concerns.md) rather than here; an ADR records a decision
that changed the design, while that document records one that did not.
