# Reactive State-Model Server Refactor Handoff

## Objective

Finish the server-side reactive-system redesign described by roadmap phases 1–4. The active work is the state-model refactor, specifically the phase 3 attribute-hierarchy replacement followed by the phase 4 wire-contract cutover. Component-system implementation is not the next workstream.

The current branch is intentionally making a clean break from the legacy runtime. Do not add a compatibility envelope for old metadata, state, or `manifest_list` shapes.

## Design authority

Treat the design documents as the specification. Read them in this order before making further architectural decisions:

1. `design/reactive-system/design.md`
2. `design/reactive-system/state-model.md`
3. `design/reactive-system/component-system.md`
4. `design/reactive-system/roadmap.md`

For the current work, `state-model.md` is primary and roadmap phases 3–4 define the gates. Particularly relevant parts of `state-model.md` are:

- §4: remove `BaseGlueAttribute`; use definitions, bindings, and explicit field adapters.
- Mixed-grain state: values belong in `state_snapshot`, validation errors in `unsigned_data`, and stable field description in schema.
- Relations: a flat relation value is raw identity/membership; traversed relations are addressed child Glue objects.
- Hard composition boundary: a value cannot contain a `BaseGlue` recursively.
- Family pipeline and `$fields` semantics.
- §10: the new wire format.

`design/reactive-system/decisions/012-formset-is-a-keyed-collection.md` records the completed FormSet design.

## Working rules

- Work server-first and favor the designed capability over compatibility with the current implementation.
- Use the design to determine scope; use the code only to locate the implementation.
- E2E behavior is authoritative. The non-E2E suite is the phase-gate regression check.
- Make edits only. Do not stage, commit, push, clean, reset, or rewrite unrelated work.
- The worktree is extensively dirty and contains other user work. Preserve every unrelated change.
- Use `apply_patch` for every manual file edit.
- Do not add code comments unless requested.
- Prefer explicit abstractions over duck typing.
- Do not rewrite the repository's existing Ruff baseline. Lint only relevant files/rules.
- Use the `just` commands documented below because the project environment depends on them.

## Completed before the current cutover

The following state-model work is already implemented:

- Address helpers and addressed-child infrastructure.
- `BaseCollectionGlue` and collection identity/reconstruction for QuerySet, Sequence, and FormSet families.
- QuerySet batch/seek work, row Glue objects, and recursion fixes.
- `BaseCollectionGlue._bind_children()` no longer accepts `owner_address`.
- FormSet was redesigned as a keyed collection of `FormGlue` children.
- `Glue.FormSet` aliases `FormSetGlue`; `Glue.formset()` is the only public construction shortcut.
- FormSet identity signs the form class, concrete formset class, `min_num`, `max_num`, and `can_delete`.
- FormSet reconstruction preserves custom subclasses and their `clean()` method.
- Sequence reconstruction preserves signed item keys.
- ADR 012 is accepted and marked implemented, with consumer migration deferred to phase 6.

The non-E2E suite was green at this point: `507 passed, 41 deselected`.

FormSet behavior still outstanding, but not the immediate attribute-cutover task:

- Enforce `min_num` and `max_num` in `validate()` and `append()`.
- Add a remove operation.
- Make `can_delete` affect behavior rather than merely being signed identity.

## Recently completed in the state-model refactor

### Child binding and policy identity

- `BaseGlue._bind_children()` and `GlueChildBinder.bind()` no longer accept `owner_address`; child addresses derive from `self.owner.address`.
- Reconstructed Glue objects restore `_address` from the signed policy before binding children.
- QuerySet's remaining internal `owner_address` usage is intentional: it builds/deduplicates relation-child addresses and is a separate concern.
- `GluePolicy.from_glue_object()` no longer recursively embeds child policies in attributes. Child identities live only in the signed shallow `children` collection.
- Model and QuerySet identities sign `fields`/`exclude` and reconstruct from identity rather than inferring them from policy attributes.
- `test_project/gorilla/models.py` now exposes `GorillaService` through an explicit `Glue.namespace(...)`.

### Definition/binding model

- `_LegacyGlueAttributeCollector` was removed from `django_glue/glue/attributes/collector.py`.
- `BaseGlue` now owns an attribute registry and bound attributes.
- `GlueAttributeDefinition` now carries `is_identity` and an optional explicit adapter.
- `BoundGlueAttribute` supplies `schema()` and `unsigned_data()` through its definition's adapter.
- Ordinary values are checked for JSON serializability and recursively reject embedded `BaseGlue` objects.
- Default `BaseGlue.get_state()` serializes value definitions only.
- Default `BaseGlue.get_metadata()` centrally projects attribute metadata.
- A transitional `BoundGlueAttribute.metadata` property delegates to that central serializer. It should disappear during phase 4 rather than become a second contract.

### Explicit Django field adapters

New modules:

- `django_glue/glue/attributes/adapter.py`: abstract `GlueAttributeAdapter` with `schema()` and default `unsigned_data()`.
- `django_glue/glue/objects/django/field_adapter.py`: `FormFieldAdapter` and `ModelFieldAdapter`.

These adapters are leaf adapters for schema and unsigned field data. They do not own the state, policy, or metadata envelopes; those remain centralized in `BaseGlue`.

FormGlue and ModelGlue now provide adapters through `get_attribute_adapters()`. Their state methods hydrate family-specific data and then use the shared BaseGlue serializer. QuerySet no longer copies row-model fields into the collection object's metadata.

### Relation representation

- Flat foreign keys are raw identity leaves such as `red_corner_id`.
- Flat to-many and reverse membership use raw leaves such as `skills_ids` and `fights_as_red_corner_ids`.
- Projected relation paths such as `skills` are addressed child Glue objects, separate from the raw membership leaf.
- `select_related()` is an ORM optimization only and no longer introduces traversal under `ALL_FIELDS`.
- Relation tests are being moved from old attribute-class internals to the public state/child interface.

## Current state: phase 3 cutover is incomplete and red

The old `BaseGlueAttribute` hierarchy has been disconnected from the primary FormGlue, ModelGlue, and QuerySetGlue paths, but its modules and exports have not yet been deleted. The focused suite currently has two failures:

```text
224 passed, 2 failed
```

Command used:

```bash
just test-app django_glue/tests/glue/test_objects.py django_glue/tests/glue/test_model_related_state.py django_glue/tests/glue/test_form_identity.py django_glue/tests/glue/test_queryset_pagination.py
```

### Failure 1: stale traversal assertion

`django_glue/tests/glue/test_objects.py::AllFieldsTestCase::test_queryset_all_fields_does_not_traverse_select_related_relations`

The test correctly asserts that `red_corner` is absent and `red_corner_id` is present, then contains a stale contradictory assertion:

```python
self.assertEqual(row['state']['red_corner']['name']['value'], 'Red Koko')
```

Delete that stale line. The designed behavior is already expressed by the surrounding assertions.

### Failure 2: premature protocol-admission assertion

`django_glue/tests/glue/test_model_related_state.py::RelatedStateTestCase::test_nested_relation_shape_is_not_admitted`

The test passes a legacy nested relation shape directly to `_load_client_state()` and expects it to be ignored, but the instance ends up pointing at `beta`. Proper rejection belongs at the phase 4 protocol-admission boundary, which does not exist yet. Do not restore nested-state parsing or codify its current accidental behavior. The likely clean move is to remove this phase-3 test and add admission-boundary coverage when the phase 4 transport contract is implemented. Verify the surrounding flat-value and null relation tests still pass.

## Next actions

### 1. Return the focused suite to green

- Remove the stale `row['state']['red_corner']` assertion.
- Resolve the nested-shape test according to the phase boundary above.
- Run the focused command until all 226 tests pass.

Completion criterion: the focused suite is green without reintroducing nested relation state or an old attribute class.

### 2. Finish removing the old attribute hierarchy

Run this inventory first:

```bash
rg -n "BaseGlueAttribute|StateAttribute|ReadOnlyAttribute|CallableAttribute|CompositeStateAttribute|GlueObjectAttribute|FormFieldAttribute|ModelFieldAttribute|ForeignKeyFieldAttribute|RelatedSetFieldAttribute" django_glue test_project --glob '*.py'
```

At handoff, production references remain in:

- `django_glue/glue/__init__.py`
- `django_glue/glue/attributes/__init__.py`
- `django_glue/glue/attributes/base.py`
- `django_glue/glue/attributes/state.py`
- `django_glue/glue/attributes/readonly.py`
- `django_glue/glue/attributes/callable.py`
- `django_glue/glue/attributes/composite.py`
- `django_glue/glue/attributes/glue_object.py`
- `django_glue/glue/attributes/django/`
- `django_glue/glue/objects/django/__init__.py`
- `django_glue/glue/objects/django/form/__init__.py`
- `django_glue/glue/objects/django/model/__init__.py`

There are also stale class-name comments/docstrings and exception wording. Remove old exports, delete obsolete modules, update imports, and rerun the inventory until no runtime dependency on the hierarchy remains. Keep the callable-operation behavior in `BaseGlue`; removing `CallableAttribute` does not remove callable Glue operations.

Before deleting modules, check whether `CompositeStateAttribute` still has a genuine caller. Do not preserve an unused abstraction merely because it remains exported.

Completion criterion: the inventory contains no old hierarchy implementation or public export; remaining occurrences, if any, are deliberately renamed exceptions/tests with current terminology.

### 3. Verify the phase 3 gate

Run:

```bash
just test
.venv/bin/ruff check --no-cache --select F <changed-python-files>
git diff --check
```

The broad Ruff baseline is pre-existing and noisy. Do not turn this task into a style rewrite.

Completion criterion: the non-E2E suite is green, focused undefined-name/import checks are clean, and `git diff --check` is clean.

### 4. Implement phase 4 from the design

Once phase 3 is green, replace the transitional old envelopes with the state-model contracts:

- Stable schema.
- Authoritative `state_snapshot` values.
- Recomputable `unsigned_data` such as validation errors and choice data.
- Explicit protocol admission/validation, including rejecting nested relation updates where only a raw identity leaf is admitted.
- Downward data split by lifetime as specified in `state-model.md` and the roadmap.

This is a removal/cutover, not a compatibility projection. Update server consumers and tests to the new contract rather than emitting both shapes.

Completion criterion: the phase 4 roadmap gate is satisfied using only the new wire contract, and the non-E2E suite is green.

### 5. Return to outstanding collection behavior

After the state-model gate, implement the remaining FormSet cardinality/removal semantics listed above unless priorities change.

## Implementation checks that still need attention

- Verify `ModelFieldAdapter` attaches only to value definitions. A projected relation child and its raw identity/membership leaf are distinct definitions.
- Verify editable `<relation>_ids` state maps correctly through ModelGlue staging and save behavior; inspect `_stage_model_attribute_value()` and `_apply_loaded_state()` before assuming the new names are fully wired.
- Verify `FormFieldAdapter` state continues to match Django `BoundField.value()` and does not leak model instances or QuerySets.
- Verify QuerySet collection metadata stays collection-scoped; row field schemas belong to addressed row ModelGlue objects.
- Remove `BoundGlueAttribute.metadata` during the phase 4 cutover once tests consume schema/state/unsigned data through the new object contract.

## Most relevant files

Core state model:

- `django_glue/glue/base.py`
- `django_glue/glue/policy.py`
- `django_glue/glue/children.py`
- `django_glue/glue/collection.py`
- `django_glue/glue/attributes/definition.py`
- `django_glue/glue/attributes/registry.py`
- `django_glue/glue/attributes/collector.py`
- `django_glue/glue/attributes/adapter.py`

Django families:

- `django_glue/glue/objects/django/field_adapter.py`
- `django_glue/glue/objects/django/model/object.py`
- `django_glue/glue/objects/django/model_fields.py`
- `django_glue/glue/objects/django/form/object.py`
- `django_glue/glue/objects/django/queryset.py`
- `django_glue/glue/objects/django/formset.py`
- `django_glue/glue/sequence.py`

Focused tests:

- `django_glue/tests/glue/test_objects.py`
- `django_glue/tests/glue/test_model_related_state.py`
- `django_glue/tests/glue/test_form_identity.py`
- `django_glue/tests/glue/test_queryset_pagination.py`
- `django_glue/tests/glue/test_declared_attributes.py`
- `django_glue/tests/glue/test_formset.py`

## Public FormSet contract already agreed

- Application formsets subclass `Glue.FormSet`.
- `Glue.formset(request, name, target, access, min_num=, max_num=, can_delete=)` is the only shortcut; `target` is either a `Glue.FormSet` subclass or a Django form class.
- Cardinality/delete resolution is keyword argument, then class variable, then built-in default.
- `clean(self, forms: list[forms.BaseForm]) -> list[str]` receives ordinary Django forms, never FormGlue wrappers.
- A collection starts empty; `min_num` is a validation floor, not an instruction to create blank rows.
- Identity is `{form_class_path, formset_class_path, min_num, max_num, can_delete}`. Prefix, management form, and `extra` are not part of identity.
- Reconstruction resolves the concrete formset class and reads its `form_class`; only the base FormSetGlue case falls back to signed `form_class_path`.

## Handoff warning

The worktree contains a much larger reactive-system branch, including client and documentation edits that are outside this immediate server task. Treat the existing tree as user-owned. Continue the narrow state-model cutover in place and inspect every overlapping diff before editing.
