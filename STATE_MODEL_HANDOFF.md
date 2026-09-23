# Reactive State-Model Server Refactor Handoff

## Objective

Finish the reactive-system redesign described by the roadmap. Phases 1–5 and phase 6 A1–A5 are implemented in `v1.1/base`. The component port, docs rewrite, and library gates are complete; consuming-project migration and production-shaped payload measurement remain before release review.

The current branch is intentionally making a clean break from the legacy runtime. Do not add a compatibility envelope for old metadata, state, or `manifest_list` shapes.

## Design authority

Treat the design documents as the specification. Read them in this order before making further architectural decisions:

1. `design/reactive-system/design.md`
2. `design/reactive-system/state-model.md`
3. `design/reactive-system/component-system.md`
4. `design/reactive-system/roadmap.md`

For the current work, `state-model.md` is primary and roadmap phase 6 defines the release gate. Particularly relevant parts of `state-model.md` are:

- Mixed-grain state: values belong in `state_snapshot`, validation errors in `computed_data`, and stable field description in schema.
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
- Use the `Edit`/`Write` tools for every manual file edit (no shell edits).
- Do not add code comments unless requested.
- Prefer explicit abstractions over duck typing.
- Do not rewrite the repository's existing Ruff baseline. Lint only relevant files/rules.
- Use the `just` commands documented below because the project environment depends on them.

## Environment

- Checkout: `/home/chasemossing/stratus-dev/django-glue`, branch `v1.1/base`.
- The state-model implementation was committed on `v1.1/state-model` as `9e1e9bb` before merging into `v1.1/base`. The earlier phase 6 A1–A4 checkpoint is `0edc83a`; the initial shelved baseline was `44803c0`.
- The checkout's `.venv` is bound to this directory. `client_js/dbg_tmp.mjs` remains an untracked user file and is excluded from the merge.

## Phase 3: attribute-hierarchy removal — COMPLETE

Deleted modules:

- `django_glue/glue/attributes/base.py` (`BaseGlueAttribute`)
- `django_glue/glue/attributes/state.py` (`StateAttribute`)
- `django_glue/glue/attributes/callable.py` (`CallableAttribute`, `LoadedAttributeCall`)
- `django_glue/glue/attributes/readonly.py` (`ReadOnlyAttribute`)
- `django_glue/glue/attributes/composite.py` (`CompositeStateAttribute`)
- `django_glue/glue/attributes/glue_object.py` (`GlueObjectAttribute`)
- `django_glue/glue/attributes/django/` tree (`BaseDjangoFieldGlueAttribute`, `FormFieldAttribute`, `ModelFieldAttribute`, `ForeignKeyFieldAttribute`, `RelatedSetFieldAttribute`)

Rewritten exports (new-model names only):

- `django_glue/glue/attributes/__init__.py`
- `django_glue/glue/__init__.py`
- `django_glue/glue/objects/django/__init__.py`
- `django_glue/glue/objects/django/form/__init__.py`
- `django_glue/glue/objects/django/model/__init__.py`

Exception rename (no client references existed to the class or the old wire code):

- `GlueCalledStateAttributeError` → `GlueCalledNonCallableAttributeError`
- code `called_state_attribute` → `called_non_callable_attribute`
- message now reads "Only callable attributes can be called."
- The class name necessarily contains "CallableAttribute" — it refers to the current-terminology callable attributes, and is the only remaining inventory match.

Stale comment/docstring updates:

- `django_glue/glue/objects/django/model/object.py` — `delete()` comment rewritten to the corrected current facts (see the ModelGlue hydration finding below).
- `django_glue/glue/objects/django/form/mixin.py` — identity comment now references `FormGlue._get_form_attribute_value()`.
- `django_glue/tests/glue/test_objects.py` — form-field docstrings now use current terminology.

Gate results:

- Inventory `rg` for the old class names: only the renamed exception remains (deliberate, current terminology).
- Focused suite (`test_objects.py`, `test_model_related_state.py`, `test_form_identity.py`, `test_queryset_pagination.py`): 225 passed.
- `just test` (non-E2E): **487 passed, 41 deselected**.
- `ruff check --no-cache --select F` on changed files: no new findings. Three pre-existing F401s in `form/mixin.py` (unused `Any`, `MutableMapping`, `BaseModel` imports) exist at baseline `44803c0` and were left alone per the baseline rule.
- `git diff --check`: clean.

## Phase 4 entry item: ModelGlue hydration cutover — COMPLETE

ModelGlue client-state hydration now runs through the attribute pipeline, per state-model.md §4 (reconstruct → apply the draft for editing → derive output → rebase on save):

- `ModelGlue._load_client_state` (object.py:551) calls `super()._load_client_state(state)` — admitted updates land in `_editable_draft` via `apply_update` → `_stage_model_attribute_value` — then applies the draft to the instance (`_apply_draft_to_instance`, object.py:559) and file uploads from `request.FILES` (`_apply_file_fields`, object.py:571). The legacy `_apply_state` direct-setattr path and `_related_pk_from_state` nested-shape resolution are deleted.
- File fields never enter the draft: `_stage_model_attribute_value` skips FileField/ImageField (their values arrive via `request.FILES`, not JSON state; the echoed descriptor dict is never setattr'd onto the instance).
- `save()` applies M2M membership from the draft (`_apply_m2m_state(self._editable_draft)`) and then `_rebase_draft()` (object.py:624) rebases the draft onto the instance's post-save values (coerced types, FK pks, M2M membership), so the successor state reflects server values.
- `_validate`'s error gate is now `not self._editable_draft` (was `_loaded_state is None`); errors still reflect the edit buffer, since the draft is applied to the instance before validation.
- Deleted: `_loaded_state`, `_apply_state`, `_related_pk_from_state`. Kept: `_get_file_from_request`, `_pk_from_related_value` (M2M pk shape).

Design notes:

- In this Django version `ManyToManyField.concrete` is `True`, so M2M fields are in the derived `editable` set and the M2M save path is live (pinned by `test_model_save_normalizes_rich_relation_and_file_state`). The prior "not wired" suspicion was half right: M2M save was live via `_loaded_state`, but the draft was not involved.
- The instance is the editing buffer (draft applied on load) — this matches the test suite's split expectations: `apply_update` stages draft-only (`test_model_definitions_stage_editable_drafts` asserts the instance is untouched), while `_load_client_state` updates the instance (related-state tests).
- The `delete()` hazard (uncoerced draft values on the instance) remains until serializer coercion; the `delete()` comment was updated to the post-cutover facts.
- The E2E docstring at `tests/e2e/test_gorilla_app.py:310` still references the removed `_related_pk_from_state`; the FK round-trip behavior it describes is unchanged. Fix the reference when E2E is next touched.

Gate results:

- Focused (`test_objects.py`, `test_model_related_state.py`): 186 passed.
- `just test` (non-E2E): **487 passed, 41 deselected** — identical to the phase 3 gate.
- `ruff check --select F` (full tree): no new findings. Six pre-existing findings, all at baseline `44803c0`: 3 in `form/mixin.py` (unused `Any`, `MutableMapping`, `BaseModel`), 1 in `glue/function.py`, 1 in `objects/django/cursor.py`, 1 in `tests/glue/test_queryset_pagination.py`. The phase 3 "three pre-existing" count covered changed files only.
- `git diff --check`: clean.

## (4a) — COMPLETE: signed state_snapshot + request updates + protocol admission

### Conformance record (pre-edit, per design/AGENTS.md)

1. **Active roadmap phase and gate.** Phase 4 internal checkpoint (roadmap.md). This increment is the (4a) sub-step: signed `state_snapshot` + request `updates` + protocol admission. The phase 4 gate ("unchanged field/interface metadata is not resent") is reached only by the follow-up (4b) (schema + `computed_data` + omission rules); the client reconciliation is phase 5, the batch envelope/per-address failures are phase 6.
2. **Governing specification sections.** state-model.md §5 (token carries `state_snapshot`; upward payload is the client-computed `updates` diff; server verifies token, reconstructs, hydrates, admits, derives, returns successor token); §10 (token envelope fields incl. `state_snapshot`/`children`/`temporal`; request shape `{address, policy_token, updates, call}`; "The request does not submit retained values as mutable fields"; protocol admission stage 1 — declaration, signed capability, path, shape, limits, "Glue does not issue a partially advanced successor token"; domain validation stage 2 — failed save still acknowledged in the successor snapshot); §4 (ModelGlue draft semantics).
3. **Legacy mechanisms removed.** The request `state` field (full `{path: {'value': ...}}` envelope echo) is removed from the wire and replaced by flat `updates`; the base `_load_client_state` `{'value': ...}` extraction is removed (upward is flat); the signed policy token gains `state_snapshot`, so retained values no longer travel client→server as mutable fields.
4. **Mapping to spec.**
   - `GluePolicy.state_snapshot` (signed) → §10 token envelope `state_snapshot` ("point-in-time copy of non-parameterized retained state the server must hydrate on the next request").
   - `BaseGlue._retained_state()` hook (+ ModelGlue draft, FormGlue bound values overrides) → populating `state_snapshot` at token issue; "server-acknowledged editable drafts, which may be domain-invalid".
   - Request field `updates` + `AttributeCallRequestContext.target_glue_updates` → §10 request shape ("client-computed updates diff containing editable paths only").
   - `BaseGlue._admit_updates(policy, updates)` → §10 protocol admission stage 1: current declaration (VALUE + EDITABLE_STATE), signed capability (`policy.attributes`), resource limits; raises `GlueRequestError(INVALID_UPDATES)` before the action runs (no successor token).
   - ModelGlue `_admit_updates` leaf rules (raw identity for FK/O2O, flat identity list for M2M, no file-path updates, JSON documents exempt) → "rejecting nested relation updates where only a raw identity leaf is admitted".
   - FormGlue `_admit_updates` leaf rules (raw choice value / flat choice list) → same rule for ModelChoiceField leaves.
   - `BaseGlue._load_client_state` flat rework + `process_attribute_call` rewiring (admit → merge snapshot+updates → apply) → §10 "hydrates retained values from state_snapshot, performs protocol admission on updates, applies admitted drafts, invokes the action, and issues a new token".
   - `DJANGO_GLUE_MAX_UPDATES` / `DJANGO_GLUE_MAX_UPDATES_ENCODED_BYTES` settings → §10 admission "resource limits" (defaults: 200 paths / 64 KiB; the five-layer transport bounds are (4b)/phase 6 work).
5. **Deliberately deferred (not in (4a), recorded so they are not lost):** schema channel, `computed_data`, token/`computed_data` omission rules, and removal of the response `state`/`metadata` echo (→ 4b; the response `state` echo is a transitional consumer surface until the client migrates in phase 5 — it duplicates the signed snapshot on the wire only for this checkpoint); serializer-registry coercion of admitted values (§7); `takes_client_state`/`updates_client_state` flag removal (§9, phase 5 with the client migration); effects/dispose, batch `objects` envelope, per-address failures (phase 6); client three-way reconciliation (phase 5). The E2E suite drives the not-yet-migrated JS client (which still posts `state`); it is expected to be red on the attribute-call flow until the phase 5 client work. The non-E2E suite is the gate for this increment.

### Implementation notes (as built)

- **Signed snapshot.** `GluePolicy.state_snapshot: dict[str, Any]` is a top-level signed field (`policy.py:54`), populated at issue time from `glue_object._retained_state()` (`policy.py:94`). `BaseGlue._retained_state()` returns `{}` (base.py:341); `ModelGlue` returns `dict(self._editable_draft)` (the acknowledged edit buffer — empty on a fresh object); `FormGlue` returns `{name: self._get_form_attribute_value(name) for name in self.editable}` (draft-first getter, so ModelChoice values are the reduced pk shape, not Model instances).
- **Request wire.** `updates` JSON field replaces `state`; `AttributeCallRequestContext.target_glue_updates` replaces `target_glue_client_state`; the context factory validates it is a JSON object (`context.py:107`). Base `process_attribute_call` now runs: `_admit_updates(policy, updates)` → `_load_client_state({**policy.state_snapshot, **updates})` → `_invalidate_attributes()` → action → successor token (base.py:482-485). No compatibility path — the `state` field is not read.
- **Protocol admission.** `BaseGlue._admit_updates(policy, updates)` (base.py:346): non-dict → reject; `DJANGO_GLUE_MAX_UPDATES` (200) count and `DJANGO_GLUE_MAX_UPDATES_ENCODED_BYTES` (64 KiB) size limits (new defaults in `django_glue/settings.py`, live via `conf.settings` so `override_settings` works in tests); per path — must be a declared `VALUE` attribute with `value_role == EDITABLE_STATE` and present in the signed `policy.attributes` (str entries only, since the field is typed `list[str | Self]` for nested child policies). Violations raise `GlueRequestError(code=INVALID_UPDATES)` (new code in `exceptions.py`) before the action, so no successor token is issued.
- **Leaf shape rules stay family-local (deliberate — not hoisted to base):** the relation-identity-leaf rule (§10 "rejecting nested relation updates where only a raw identity leaf is admitted") is implemented inline in `ModelGlue._admit_updates` (FK/O2O raw identity or None, M2M flat identity list, file paths rejected, JSONField exempt) and `FormGlue._admit_updates` (ModelChoiceField raw value, ModelMultipleChoiceField flat list). Rationale: `BaseGlue` is family-agnostic, and §7 assigns leaf-shape knowledge to the serializer registry — a base method would be a stand-in for a contract the spec requires, which the registry later displaces.
- **FormGlue cutover (the last legacy hydration bypass):** `_load_client_state` now calls `super()._load_client_state(state)` (staging `_editable_draft` through the attribute pipeline) then `self.form = self._bind_form()`; `_bind_form` reads `self._editable_draft.get(field, self.form[field].value())` flat (no envelope extraction); `_loaded_state` deleted. `FormSetGlue._load_client_state` is unchanged: it keeps the legacy keyed container shape `{'forms': {key: ...}}` (§8 collection identity/keys work owns that), but each per-form dict delegated to the child is now flat.
- **Tests.** New `django_glue/tests/glue/test_update_admission.py` (24 tests): protocol admission (empty/no-op, non-dict, count limit via `override_settings`, size limit, unknown path, non-editable path, outside signed capability via a narrowed re-signed policy, pass-through, full-flow merge-over-snapshot, admission failure before the action); ModelGlue leaf shapes (nested FK rejected, flat pk admitted, M2M list-of-objects rejected, flat list admitted, file path rejected); FormGlue choice leaves (nested rejected, flat admitted, both field kinds); snapshot contract (fresh = empty, acknowledged draft signed in, reconstruction hydrates snapshot+updates, successful save rebases successor snapshot, failed save retains draft in successor snapshot and leaves the row untouched). All pre-existing test call sites migrated from the `{path: {'value': ...}}` envelope to flat values and from `target_glue_client_state`/POST `state` to `target_glue_updates`/POST `updates` (`test_objects.py`, `test_model_related_state.py`, `test_form_identity.py`, `test_formset.py`, `test_add_creation.py`, `test_operation_view.py`, `test_callable_parameters.py`, `test_authorization.py`). Response-side `assertIn('state', ...)` assertions are kept — the downward echo is transitional until (4b)/phase 5.

### Gate results

- Focused (the 9 touched/added test files): 272 passed.
- `just test` (non-E2E): **511 passed, 41 deselected** (487 baseline + 24 new).
- `ruff check --select F` (full tree): no new findings (same 6 pre-existing at baseline `44803c0`).
- `git diff --check`: clean.

## (4b) Conformance record — static_data + computed_data + omission rules (per design/AGENTS.md)

1. **Active roadmap phase and gate.** Phase 4 (roadmap.md internal checkpoint). Gate: *"Unchanged field/interface metadata is not resent."* This increment (4b) builds the phase-4 downward channel: the `static_data` channel, the `computed_data` channel, the derived omission rules, and the removal of the transitional response `state`/`metadata` echo. The (4a) signed `state_snapshot` already carries the acknowledged editable half of the old `state` echo; (4b) removes the rest.

   **Wire-key decisions (decided in review):** the two downward channels are keyed by *volatility*, not by the security property they share (both are outside the policy-token signature, never sent back, and hold no bearing on future server state).
   - Stable interface channel: `static_data` (draft names `schema`, then `view_data`, rejected: `schema` shadows pydantic's legacy `BaseModel.schema` attribute, and the alias plumbing (`schema_`/`by_alias=True` at every dump site) needed to keep that name was rejected). It is a function of declaration and access — stable for the token's lifetime, resent only when the interface itself changes.
   - State-dependent channel: `computed_data` (renamed from `unsigned_data` because "unsigned" describes the boundary both channels share, not the distinction between them). It is a function of current state, re-derived as the request touches it.
    All four design docs were updated at the wire-key sites; the spec's former "explicit `unsigned_` prefix" section now states the shared unsigned boundary instead; concept-level "schema" prose (schema compilation, descriptors) is unchanged.

    **Snapshot-baseline decision (decided in review 2026-09-18):** the (4b) test migration exposed that the (4a) drafts-only `state_snapshot` left the client's canonical view incomplete — a freshly introduced `ModelGlue` row (or any ADD/CHANGE row) had *no channel* carrying its current editable values (snapshot = acknowledged drafts only, empty at introduction; `computed_data` is "the server recomputes or ignores"). Settled Livewire-style: the snapshot is the complete resolved state of every exposed editable path (the token is the client's full baseline). Pinned in state-model.md §4 (family table + Django-adapters paragraph). Code:
    - `ModelGlue._retained_state()` signs resolved values (`_get_model_attribute_value` — draft first, else the row's current value) for every editable path.
    - `ModelGlue._load_client_state()` stages only snapshot values that differ from the re-fetched row (`_matches_row_value`, JSON-normalized through `GlueResponseJSONEncoder` — the same encoder the token serializer round-trips) into `_editable_draft`, so the draft stays "edits only" (the `_validate` guard, `_rebase_draft`, and m2m application all depend on that).
    - `BaseGlue._retained_state()` signs RECONSTRUCTOR value attributes into the snapshot (spec: it "contains internal reconstructors"; the §10 worked example's `loaded_row_count` is one); ModelGlue/FormGlue merge their family state on top via `super()`.
    - `QuerySetGlue.get_computed_data(include_all=True)` adds the current page (`items`/`seek_key`/`has_next`/`batch_size`) to the EAGER manifest — the family table's down-only half ("rows, annotations, counts, and keyed child references"); later pages still arrive as `query_with_params` method results.
    - FormGlue was already full (initial/bound data *is* the form's retained state); unchanged.
    - Tests: `test_update_admission.py` pins the baseline + delta (fresh object signs row values; re-request with no edits keeps the draft empty; snapshot values matching the row do not enter the draft).
 2. **Governing specification sections.**
   - state-model.md §4 "Three current tangles" (the mixed-grain split: `ModelFieldAttribute.state` combines editable `value` → `state_snapshot`, derived `errors` → `computed_data`, stable interface metadata → `static_data`).
   - §5 (the response carries a successor policy token plus `computed_data`, not a server-computed diff; "the response carries a successor policy token plus `computed_data`"; omission semantics — omitted ≠ empty).
   - §10 wire format (page-load entry `{address, policy_token, static_data, computed_data}`; response entry; "Responses omit what did not change" — token omission by comparing retained values against the verified incoming token; `computed_data` omission "derived rather than declared"; "an adapter that did not re-derive its downward output omits the key entirely").
   - §10 static data paragraph ("`static_data` describes the client-visible interface needed to construct field and attribute projections: types, labels, widgets, callable shapes, and state-path mappings. It normally ships when an address is first introduced. If that interface later changes, the server may send a replacement `static_data` atomically with the successor token and `computed_data`; unchanged `static_data` is omitted." Static data describes shape, not authority, and never returns to the server.).
   - §10 `$fields` is a client projection (`value_path` points at the field's leaf in the assembled canonical view; "Fixed field choices live in `static_data`; state-dependent choices and errors live under `computed_data.fields`; search results remain method results").
   - §10 "The explicit `unsigned_` prefix" (unsigned = outside the policy-token boundary, not an invitation to accept it from a request).
3. **Legacy mechanisms those sections remove.**
   - The response `state` echo (`{path: {'value': ..., 'errors': ...}}` mixed grain on every response) — the value half is already in the signed `state_snapshot` (4a); the output half moves to `computed_data`.
   - The response/manifest `metadata` envelope (`{attributes: {path: {namespace markers / adapter schema}}}`) — replaced by the `static_data` channel.
   - `BaseGlue.metadata` / `get_metadata` / `_get_attribute_metadata`, `BoundGlueAttribute.metadata`, and the family `get_metadata` overrides (template/function/sequence/formset).
   - The manifest `state` key — replaced by `computed_data`; the manifest gains `address` and `static_data`.
   - `ModelFieldAdapter`/`FormFieldAdapter`: state-dependent `selected_choice(s)` and `choices_cache_key` leave `schema()` and move to `computed_data()` (the adapter's complete state-dependent output, per `$fields`).
4. **Mapping to spec.**
   - `BaseGlue.get_static_data()` → §10 "static data describes the client-visible interface": `fields` (adapter schema with `value_path`, types, labels, widget, fixed choices), `children` (`{kind: <namespace>, nullable}` from the child declaration), `callables` (`{allowed_arguments}`); stable across calls for an unchanged interface (no fingerprint/selected values remain in it).
   - `BaseGlue.get_computed_data(include_all=False)` → §5/§10 "complete current down-only output": derived property values at top level (only for paths re-derived this request), and re-derived adapter output under `fields.{path}`. `include_all=True` is the introduction surface (page load), where every value is fresh by construction.
   - Freshness: a single per-adapter derivation event — `BaseGlue._derived_paths` (marked by `_load_client_state`/`apply_update`, by `BoundGlueAttribute.get()` for DERIVED_OUTPUT values, and by the save/validate actions marking their projected fields) → §10 "an adapter that did not re-derive **its** downward output omits the key entirely" — one derivation event per adapter, omission is derived, not flagged. Base holds no channel-specific freshness flags: the adapter owns what its output contains (field adapters include the current selection *and* their validation errors in one `computed_data()`); base only gates *whether* the adapter re-derived.
   - `BaseGlue._retained_values_equal(incoming, successor)` + conditional `policy_token` in `process_attribute_call` → §10 token omission ("Glue compares the object's retained values … against the values the verified incoming token carried … the entry simply omits `policy_token` and the client keeps the token it has").
   - Conditional response payload in `process_attribute_call` (`policy_token`/`static_data`/`computed_data` each present only when changed/re-derived, else `result`+`messages` alone) → §10 response envelope.
   - `GlueManifest` (`address`, `policy_token`, `static_data`, `computed_data`, `loading_strategy`) → §10 page-load/introduction entry (introduction always carries static data + computed_data).
   - `GlueAttributeAdapter.schema()/computed_data()` → §10 `$fields` (fixed choices in `static_data`; the adapter's complete current state-dependent output — for fields: selected choices + validation errors — under `computed_data.fields`). The adapter always includes the `errors` key once derived (empty included) so a cleared validation is distinguishable from "not re-derived" omission.
   - `FunctionGlue.get_static_data()` adds `params` (name+type per callable parameter) → §10 "callable shapes".
5. **Deliberately deferred (recorded so they are not lost).**
   - Serializer-registry coercion of admitted values (§7) — (4c); it also closes the residual uncoerced-draft `TypeError` hazard.
   - Removal of the inert `takes_client_state`/`updates_client_state` declaration flags (§9 "Deleted") — phase 5; they are inert server-side today (collector drops them) and the client still reads `takes_client_state` from the old metadata shape (client_js/src/proxies/base.js), so their removal ships with the client migration.
   - The `effects` channel (messages/redirect/events/dispose as a first-class response field, §6) and the flat `objects` envelope (phase 6); `messages` stays in the transitional response payload for now.
   - The `load_state` method keeps its legacy `{path: {'value', 'errors'}}` envelope as a **method result** (spec: "search results remain method results" — method results are free-form); the channel cutover does not reshape it.
   - E2E stays red until the phase 5 client migration (the JS client still reads `state`/`metadata` and posts `state`). The non-E2E suite is the gate for this increment.

## (4c) — COMPLETE: serializer-registry coercion

### Conformance record (pre-edit, per design/AGENTS.md)

1. **Active roadmap phase and gate.** Phase 4, after the phase gate ("unchanged field/interface metadata is not resent") is already green. This (4c) increment implements only serializer-registry coercion of admitted editable updates and signed editable snapshots before they are applied. The phase-5 client migration remains the next workstream. The inert `takes_client_state` / `updates_client_state` flags remain until that migration because the current client still reads the former.
2. **Governing specification sections and accepted decisions.** state-model.md §4 (one attribute pipeline; family adapters own leaf conversion; ModelGlue's signed snapshot is the full row-baseline-plus-draft view and its internal draft remains edits only); §7 (the declared annotation names the target type, a public registerable serializer registry owns conversion, a missing annotation falls back to the registry or leaves the value untouched, and built-ins cover Django's common types); §10 (decoding and malformed/unsafe shapes are protocol admission, before the action and without a successor token; domain validation remains separate and validly typed but domain-invalid drafts are acknowledged). The settled §4/§5/§10 decisions remain unchanged: `static_data` / `computed_data`, full-snapshot baseline, single-derivation-event freshness, and the adapter split.
3. **Legacy mechanisms removed or prohibited.** Raw admitted values may no longer pass unchanged from `_admit_updates()` into `_editable_draft` and a model instance when a declared or adapter-derived target type exists. Model/form relation and file leaf-shape checks no longer live in family `_admit_updates()` overrides as a temporary stand-in for §7; registered Django-field serializers own those shapes and conversions. No compatibility path preserves uncoerced model numeric/date/identity strings. `GlueResponseJSONEncoder` is not reused as an inbound decoder. Domain validators are not pulled into protocol coercion: for example, a model integer string is decoded to `int`, while min/max validation remains `Model.full_clean()` work.
4. **Mapping to the specification.**
   - `GlueSerializerHandler` → §7's consuming-project extension seam for value-type conversion.
   - `GlueSerializerRegistry.register()` / `coerce()` / `decode()` and the shared `glue_serializer_registry` → §7's public registry and built-in dispatch.
   - Annotation, Django model-field, and Django form-field handlers → §7's missing-annotation fallback and common-Django-type coverage; form scalar data stays raw for Django's bound-form semantics, while model leaves and relation identities are typed before instance application.
   - `GlueAttributeDefinition.value_type` → the declared annotation's "what" half, independent of declaration and role.
   - `GlueAttributeAdapter.coerce()` / `decode()` plus `BoundGlueAttribute.coerce_update()` / `decode_retained()` → adapter-owned conversion for projected Django leaves and the common attribute-pipeline conversion points for untrusted updates and trusted signed snapshots.
   - `BaseGlue._admit_updates()` → §10 protocol decoding/coercion of current-declaration + signed-capability updates; malformed coercions raise `INVALID_UPDATES` before the action.
   - `BaseGlue.process_attribute_call()` snapshot coercion → signed JSON representations are restored to the same Python leaf types on later requests before hydration, without double-coercing newly admitted updates.
5. **Deliberately deferred.** `takes_client_state` / `updates_client_state` removal and all JavaScript serializer/parser migration ship with phase 5. The broader outbound replacement of `GlueResponseJSONEncoder` is not part of this inbound-coercion increment. Effects, the flat batch envelope, and per-address failure transport remain phase 6.

### Implementation notes (as built)

- **Public registry.** `django_glue.serialization` adds the public `GlueSerializerHandler`, `GlueSerializerRegistry`, `GlueSerializerError`, and shared `glue_serializer_registry`, exported from `django_glue`. Project handlers register ahead of built-ins. The registry leaves a value untouched when no handler supports its target.
- **Two inbound directions.** Handlers implement `coerce()` for untrusted updates and `decode()` for trusted signed snapshots. The distinction keeps file placeholders and FormGlue's raw bound-data semantics valid while still restoring JSON-encoded typed ModelGlue/declared values on later requests.
- **Built-ins.** The annotation handler uses pydantic `TypeAdapter`; the model-field handler uses Django field conversion for scalar fields and target-field conversion for FK/O2O/M2M identities, keeps JSON documents structured, and rejects file-value updates; the form-field handler preserves raw scalar bound data while enforcing ModelChoice leaf shapes and rejecting file-value updates.
- **Attribute pipeline.** `GlueAttributeDefinition.value_type` carries resolved declared annotations. `BoundGlueAttribute.coerce_update()` uses an adapter when present, otherwise the annotation or current value type; `decode_retained()` mirrors that for the signed snapshot. `BaseGlue._admit_updates()` converts only after declaration/capability checks and translates coercion failure to `INVALID_UPDATES`; `process_attribute_call()` decodes the untouched signed snapshot before merging the already-coerced updates.
- **Temporary family stand-ins removed.** `ModelGlue._admit_updates()` and `FormGlue._admit_updates()` are deleted. Their relation/file shape rules now belong to the registered Django handlers. The stale `ModelGlue.delete()` hazard comment is removed because valid numeric strings are typed before the draft reaches the instance.
- **Validation boundary.** Malformed model values such as a non-numeric integer string fail protocol admission before the action. Values that decode correctly but violate domain rules (the pinned case is integer `0` below a `MinValueValidator(1)`) still reach `Model.full_clean()`, remain in the successor snapshot as typed drafts, and leave the database row unchanged.
- **Tests.** `test_update_admission.py` now covers annotated-value coercion, malformed annotated/model rejection, project handler registration, missing-target pass-through, string-to-PK conversion for FK/M2M leaves, raw FormChoice preservation, a signed DateTime snapshot round-trip, typed domain-invalid draft retention, and the former model arithmetic `TypeError` path.

### Gate results

- Focused admission/serializer suite: **34 passed**.
- Model/form/adapter regression set (`test_objects.py`, `test_model_related_state.py`, `test_form_identity.py`): **191 passed**.
- `just test` (non-E2E): **520 passed, 41 deselected** (513/41 before (4c), +7 tests).
- `ruff check django_glue --select F`: exactly the same 6 pre-existing findings recorded after (4b); no new findings.
- New serializer module full Ruff check: clean.
- `git diff --check`: clean.

## Phase 5 — COMPLETE: address registry and role-aware client reconciliation

### Conformance record (pre-edit, per design/AGENTS.md)

1. **Active roadmap phase and gate.** Phase 5 is explicitly authorized. Its gate is: one proxy exists per live address; newer local `ABC` survives when `A -> AB` was sent and `AB` returns; namespace and child paths route through the correct address and policy token. Phase 5 migrates the current page-manifest and single-address response transports onto the new client runtime. Phase 6 still owns the flat `objects` envelope, effects/disposal, per-address failures, reintroduction, and consumer migration.
2. **Governing specification sections and accepted decisions.** state-model.md §4 "Client object graph" (one address registry owns one stable Alpine-reactive proxy and request queue per live address; one attribute materializer, child binder, and response dispatcher; family proxies do not own transport or reconciliation); §4 `$fields` (stable field proxies over `value_path`, static descriptors plus `computed_data.fields`); §5 (canonical/ephemeral/reactive, `diff(canonical, ephemeral)`, omitted versus empty halves, three-way reconciliation, mutation revisions captured when a request is sent, per-address request ordering); §7 (remove client `parseFieldValue` special-casing); §9 deleted declarations (`takes_client_state`, `updates_client_state`, `LoadingStrategy`); §10 (decoded token supplies state snapshot and shallow child bindings, static/computed replacement semantics, request `updates`, response omission semantics). Roadmap phase 5, not phase 6, governs the transition. Grill decisions: a dedicated internal per-address record backs stable proxy facades; the useful public proxy API remains stable and the registry stays private; current transports normalize to one internal addressed-entry dispatcher without accepting multiple external wire formats; failed operations reject individually and release the queue with held state unchanged; work proceeds through state-engine, materializer/family, and integration checkpoints.
3. **Legacy mechanisms removed or prohibited.** The client no longer reads response/manifest `state` or `metadata`, posts `state`, filters state per callable, recursively merges `_state`, keys proxy identity by namespace/name, reconstructs children from recursively decoded policy objects, or keeps per-family child/response caches. `_state`, `_metadata`, `_mergeState`, `_stateForAttribute`, `parseFieldValue`, and client reads of `takes_client_state` are removed rather than wrapped. The inert Python declaration options `takes_client_state` and `updates_client_state` are deleted with their call sites. No compatibility envelope accepts both legacy and new keys. `manifest_list` remains only as the phase-5 outer page/result transport; its entries use `address`, `policy_token`, `static_data`, and `computed_data` until phase 6 replaces the outer envelope.
4. **Mapping to the specification.** The planned internal `GlueAddressRecord` owns an address's held token/policy halves, static/computed data, canonical and Alpine-reactive values, mutation revisions, generation, stable proxy, and serialized request queue (§4/§5). `GlueAddressRegistry` owns exactly one record/proxy per live address and the namespace/name public lookup aliases (§4 and the phase gate). Reconciliation utilities assemble the authoritative view from the newest held token/computed halves, derive outgoing updates, and apply the §5 three-way patch while preserving newer editable mutations. `GlueAttributeMaterializer` projects stable namespaces, direct value/callable properties, and stable `$fields` from `static_data` (§4 `$fields`). `GlueChildBinder` resolves the decoded shallow `children` map through the address registry instead of embedding child state (§4/§10). `GlueResponseDispatcher` registers introduction shells before applying normalized addressed entries and is the single response-application path (§4/§10). `GlueHttp.sendAttributeRequest(..., updates, ...)` sends the client-computed flat update map and file payloads (§5/§10). Existing family proxy public methods remain facades over the shared runtime; no family receives a replacement state or transport engine.
5. **Deliberately deferred.** Phase 6 still owns the external flat `objects` request/response envelope, multi-address batching and independent failures, the first-class `effects` channel, disposal and replacement lifecycle, expired-child reintroduction, component fragments/morph sequencing, and consuming-project migration. The broader server outbound replacement of `GlueResponseJSONEncoder`, FormSet cardinality/removal behavior, polling/status conveniences, and documentation rewrite remain outside phase 5.

### Phase 5 continuation snapshot (2026-09-21)

Phase 5 is complete on the current tree: the rewritten client unit suite, the full browser suite, and the full non-E2E suite are all green (gate results below, rerun 2026-09-21 after the queryset collection-ownership fix and the collection-row reference restoration), and all three remaining review targets are resolved (see "Review target resolutions" below). The working-tree state-model work is ready for review/commit; do not start phase 6.

Implemented client runtime:

- `client_js/src/runtime/state.js` owns cloning/equality, deep mutation observation, canonical assembly, editable diffing, and sparse `computed_data` merging.
- `GlueAddressRecord` owns one address's token/policy, static/computed halves, canonical and Alpine-reactive values, editable mutation revisions, stable proxy, and serialized request queue. Request capture happens when a queued operation is sent, so later typing is included in the next call.
- `GlueAddressRegistry` owns exactly one record/proxy per address. `GlueAttributeMaterializer`, `GlueChildBinder`, and `GlueResponseDispatcher` are the shared projection/binding/application seams.
- The client reads only `address`, `policy_token`, `static_data`, and `computed_data`; posts flat `updates`; no compatibility read of legacy `state`/`metadata` remains. `parseFieldValue`, `_state`, `_metadata`, `_mergeState`, `_stateForAttribute`, and client `takes_client_state` behavior are removed.
- Family proxies remain facades. A late unit-test finding fixed generic callable materialization so it no longer overwrites specialized `QuerySet.count/get/new` or `FormSet.append/validate` methods.
- Static replacement removes obsolete projected properties. Dotted `$fields` use their full schema path for `computed_data.fields` lookup. Internal runtime references are non-enumerable so Alpine does not recurse through the client/registry cycle.
- Query views share the address record and request queue but keep independent query-result facades. Response and result manifests enter the same private registry; only intended root/fragment manifests become public namespace aliases.
- The Python declaration options `takes_client_state` and `updates_client_state` and all call sites are removed. `LoadingStrategy` remains for now; the grill explicitly did not make its removal part of this slice.

Implemented server/client integration:

- Page contexts serialize root and recursive child manifests. Attribute responses include current child manifests when the shallow child map changes, using the existing phase-5 `manifest_list` transport.
- Queryset row manifests use canonical item addresses and preserve both ordinary included fields and dotted relation projections.
- Queryset projected relations now follow the pinned ownership rule: the collection owns deduplicated relation children and row policies reference those collection-owned addresses. The latest server-only change added the `_bind_children` integration and corrected to-many relation children to use collection-owned `QuerySetGlue` entries.
- Model relation field schema exposes `choice_field`, allowing the client field facade to call `foreign_key_choices` with the server-declared path instead of inferring Django attnames.
- Gorilla demo projections use `skills__id` / `skills__name`; the foreign-key save E2E uses `$fields.red_corner.value`; validation summaries use `$fields`, not `_state`.
- `detail_page_partial.html` now has one root element, preserving the strict `renderOuterHtml` contract.

Gate results (rerun 2026-09-21 on the current tree — all current, after the row-reference fix and the four new JS gap tests):

- `just test-app django_glue/tests/glue/test_component.py -q`: **22 passed**, including the new `test_component_static_data_marks_editable_value_paths`.
- Full `just test` (non-E2E): **527 passed, 41 deselected** — 522 before this session's five new tests (two FormSet `append` introduction tests in `test_formset.py`, three collection-row reference tests in `test_model_related_state.py`), no regression.
- Full `just test-e2e -x -q`: **31 passed, 10 xfailed, 527 deselected** — rerun after the collection-row reference restoration, green. The Gorilla projected-skill flow and the foreign-key-save flow passed.
- `just js-tests`: **88 passed**, 0 failed; line coverage **89.15%** (up from 86.69% with the four new gap tests).
- `just js-build`: green; the generated bundle builds at 24.8 KB.
- `ruff check django_glue --select F`: exactly the 6 pre-existing findings recorded after (4c); no new findings.
- `git diff --check`: clean.

Continuation order (all items completed 2026-09-21 — see gate results above):

1. Done: `just test-app django_glue/tests/glue/test_component.py -q` — 22 passed.
2. Done: full `just test` — 527 passed / 41 deselected, no regression.
3. Done: `just test-e2e -x -q` after the row-reference restoration — 31 passed / 10 xfailed, green.
4. Done: `just js-tests` (88 passed) and `just js-build` (stable bundle) re-verified.
5. Done: `ruff check django_glue --select F` — exactly the 6 pre-existing findings; `git diff --check` clean.
6. Done: all three remaining review targets resolved (see "Review target resolutions" below).
7. Done: phase 5 marked complete in this snapshot; the current tree is green.

Review target resolutions (2026-09-21):

1. **FormSet `append` introductions — pinned.** Two new tests in `test_formset.py`: `test_append_attribute_call_introduces_the_new_child_in_manifest_list` (a row-level `append` call returns a `manifest_list` containing the new form's manifest — `address`, `policy_token`, `static_data` — and the response `children` map gains the new row key) and `test_attribute_call_without_child_changes_omits_introductions` (an unchanged call returns no `manifest_list` and no `children` key). 17 passed in the file.
2. **Queryset ownership review — real defect found and fixed.** The collection-owned child model (`_bind_children` / `_row_glue` / `_bind_relation_children`) is correct at introduction, but `ModelGlue._reconstruct_from_policy` re-derived a collection row's projected-relation children at **row-owned** addresses (`fights#…[1].red_corner`) instead of restoring the **collection-owned** addresses signed in the row policy (`fights#….red_corner:<pk>`). Consequences: successor policy tokens diverged from the signed ones (token churn on every row-level call) and `manifest_list` would reintroduce a duplicate proxy for the same related object. Fixed in `ModelGlue`: reconstruction now records the signed child map (`_signed_row_children`) when the identity signs `row_access` (the collection-row marker), and `ModelGlue._bind_children` replaces the re-derived projected-relation children with reference-only `BoundGlueChild`s at the signed collection addresses (non-relation children such as `form` re-derive as before; the override keeps the base `live_children`/`reintroduce` signature). Three regression tests in `test_model_related_state.py`: to-one reference restoration, to-many reference restoration, and a full `process_attribute_call` on a projected row asserting the response is quiet (no `manifest_list`, no `policy_token`). **Residual edge (phase 6):** a relation that changes out-of-band (None→set, or to a different related object) still re-derives a row-owned child at reconstruction, because pointing the row at a collection address the collection does not own requires the reintroduction protocol phase 6 owns; the common unchanged case is fully fixed.
3. **Deleted legacy JS files — decision: none restored, four gaps re-pinned in new-contract form.** All tests in the three deleted files build on the legacy `state`/`metadata`/`_state` envelope and cannot be restored as-is. Auditing each behavior against the current source and the new suite: most are already pinned by the 84 new tests (error listeners keep the rejection, untagged results are not manifests, client-init manifest validation, view GET method, file extraction, `hasErrors`, `ensureChoices`, `selectedChoice(s)`, `toggleChoice`/`removeChoice`, namespace fallback via the unregistered `dashboard` fixture) or are dead legacy mechanisms (recursive `_state`/`_applyState` merging, `parseFieldValue` date/JSON string coercion, `_resultIsManifest`). Four live behaviors were unpinned and are now covered by new tests: `$key` = `$pk ?? name` and many-relation `selectedPks`/`hasChoiceSelected`/`addChoice` (fields_form_function.test.js), `querySet.new()` returning the manifest-backed model proxy from the shared registry (proxies.test.js), and the `FileList` multipart branch (http_extra.test.js). `_mergeChoices` update-vs-append semantics stay indirectly covered through the `ensureChoices` tests.

## Phase 6 — IN PROGRESS: authoritative addressed snapshots, the flat `objects` envelope, and lifecycle

### A5 conformance record (pre-edit, 2026-09-22)

1. **Phase and gate.** Phase 6 slice A5 is authorized. The remaining gate is shared `objects` transport and E2E coverage for components and established Glue families, including child registration before binding, stable drafts, disposal, per-address batch failure, and omitted unchanged data.
2. **Governing contract.** `state-model.md` §§5, 6, 10 govern addressed state, responses, effects, refresh, and the flat envelope. `component-system.md` §§3–8 govern declared parameters, mount, Django template-tag stamping, keyed addresses, morphing, DOM identity, events, and lifecycle, as corrected by the current component implementation and its `design/components/spec.md` §3 on `e6f204b`. `roadmap.md` phase 6 owns the gate. The component workstream supplies the stamp grammar and behavior examples but targets the removed wire format.
3. **Legacy mechanisms removed.** The `glue_view` fragment, template-response result, and multi-row query-item `manifest_list` shapes must move to `objects`; component root manifests and global component names from the old branch must not become the new contract. The three-event `before`/`after`/`error` listener API gives way to declared semantic events. No compatibility envelope is introduced. The superseded `<glue:... />` compiler is not to be ported.
4. **Mapping.** Component registration and reconstruction stay behind the `component` namespace of `glue_class_registry`; declared parameters feed the generated constructor and signed target. The existing `{% glue_component 'tag-name' parameter=value key=value %}` Django template tag resolves typed filter expressions and stamps keyed components; no custom template backend is introduced. Initial and later renders produce addressed entries plus an `html` channel; the client registry associates component roots with their addresses, morphs after reconciliation, and disposes removed roots. `Glue.event()` declarations produce `effects.events`, delivered through source-scoped `$on()` and component DOM events. Remaining view/template/query consumers share the `objects` entry pipeline. `docs/` and E2E tests record the public contract.

### Conformance record (pre-edit, per design/AGENTS.md)

1. **Active roadmap phase and gate.** Phase 6, authorized 2026-09-21. Gate (roadmap.md line 55): legacy-object and component E2E tests share the envelope; child entries register before binding; stable child drafts survive owner refresh; replacement/removal disposal passes; a batch with one failing entry advances every other entry unchanged; an unchanged token or `computed_data` is omitted and the client holds its previous value.
2. **Governing specification sections.** state-model.md §10 "Wire format" (the `objects` request/response/page-load envelope; "Failure is per address, not per request" — envelope faults fail the request with the whole-response error shape, address faults fail one entry with `error` and no token/static/computed/result/effects; the closed error-code set with `not_authorized` vs `policy_expired` distinguished; "What 'newly introduced' means" — the incoming token's `children` map is the live set, the four-way slot table; "Reintroducing an expired child" — client-supplied `reintroduce` list of declared slots, same address, existing proxy/draft/scope/queue preserved; the 10-step staged client apply; "Responses omit what did not change" — derived token/computed_data omission, omission ≠ empty; transient callable results as client-registry bookkeeping, wire `result` is the address; §6 "Effects and fragments are separate channels" — `effects.messages`/`redirect`/`events`/`dispose`, disposal applied after reconciliation, recursive). component-system.md governs the component half of the gate and stays in its own workstream.
3. **Legacy mechanisms removed/prohibited.** The `manifest_list` outer transport (attribute-call responses, and later page load), the `is_glue_manifest`-tagged result objects (a callable returning a Glue object now has a wire `result` that is the introduced address), the `<object_name>/<attribute_name>` path-parameter endpoint (the envelope carries both), and the whole-response error shape for address-scoped faults (`GlueResponse.from_error` survives for envelope faults only). No compatibility envelope: the old request shape is rejected, not projected forward.
4. **Mapping to the specification (slice A1 — the attribute-call `objects` envelope).** Request: multipart body with one JSON `objects` form field, `[{address, policy_token, updates?, call: {attribute, kwargs}}]` + the existing file parts (the spec keeps "client-computed `updates` diff" and file payloads; the spec fixes the JSON entry shape, not the physical encoding, and files have no JSON representation — multipart parts stay). Endpoint: single path, no path parameters. Response: `{objects: [entry, ...]}` where the target entry carries `address` + omitted-when-unchanged `policy_token`/`static_data`/`computed_data` + `result` + `effects: {messages: [...]}`, and newly introduced children ride as their own entries (the phase-5 child manifests are the entry shape, minus the result tag). Address fault → `{address, error: {code, message}}` entry, nothing else, other entries advance (independence invariant). Envelope fault (malformed `objects`, empty batch, duplicate addresses, outer address ≠ signed address) → whole-response error, no `objects`. Callable returning a Glue object → `result` is the address string, the object's entry is included, the client registers all entries before resolving `result` to the proxy.

### Phase 6 slice plan

- **A1 (this session): the attribute-call `objects` envelope** — server endpoint + per-entry resolver with the envelope/address fault boundary and independence, response entry shape with `effects.messages` and address results, client `http.js`/`base.js`/dispatcher migration, Python + JS test migration, E2E green.
- **A2: page-load `objects` envelope** — the init context and `GlueContextManager` serialization move from `manifest_list` to `objects`; the view-fragment (`glue_view`) endpoint and its template-response shape stay on the phase-5 shape until the view/component slice.
- **A3: reintroduction protocol** — requires the policy-token lifetime decision first (roadmap security hardening: "the child-reintroduction contract in §10 depends on a known expiry; the number must be chosen before that path is implemented"; code currently uses a rolling 24 h `DJANGO_GLUE_PROXY_POLICY_MAX_AGE_SECONDS`). Server: `reintroduce` admission against declared slots, same-address factory rerun. Client: `policy_expired` marks the record stale (not disposed), proxy rejects with a recoverable error naming the owner, owner request carries the slot path. Closes the recorded phase-5 edge (out-of-band changed relations on collection rows).
- **A4: disposal + effects completion** — `effects.dispose` (explicit), replacement/removal lifecycle (same path + same address preserves proxy/draft/scope/queue; different address at a path is a replacement; absent nullable path is a removal), recursive teardown through recorded lifecycle ownership, transient-result bookkeeping (producer records drive cascade; owner disposal cascades; repeated calls mint distinct addresses).
- **A5: component envelope sharing + consumer migration + `docs/` rewrite** — the component-system workstream joins on the shared `objects` envelope; E2E for both families; the documented consumer migration (the Consequences table) and docs rewrite land here.

### A1 completion snapshot (2026-09-22)

A1 is COMPLETE and green. Gates on the current tree: 535 passed non-E2E (41 deselected), 31 passed / 10 xfailed E2E, 88 passed JS, green `js-build` (25.0 KB), ruff `-F` unchanged at the known 6-error baseline, `git diff --check` clean. Uncommitted, on top of `99d53bc`.

Implementation decisions made during A1:

- **`QuerySetGlue._row_glue(instance, *, bind=True)`** — a row constructs bound (child binding and policy signing both require a bound owner), and the binding is released before return when `bind=False`. The Glue-callable-result contract requires callables to return unbound objects (the framework owns introduction: it binds, checks the address against the live set, signs the successor token). `new()`/`get()` pass `bind=False`; the child-list and query-item paths keep the default.
- **Error-code renames to the spec names:** `proxy_access_denied` → `not_authorized`, `proxy_policy_expired` → `policy_expired`; new `ADDRESS_MISMATCH` / `DUPLICATE_ADDRESSES` envelope codes. `MISSING_PATH_PARAMETERS` is now dead (path params are gone).
- **`static_data.callables[name].returns_glue`** — set from `definition.expected_type is not None`; the client uses it to resolve an address-string wire `result` to a proxy.
- **Address faults return 200** with a per-entry `{address, error: {code, message}}` (spec: "Failure is per address, not per request"); envelope faults stay whole-response non-2xx.
- **JS test migration** — `testUtils` gains `attributeResponse(address, fields)` and `objectsEnvelope(entries)`; the fallback fetch mocks return the envelope shape; `http.test.js` asserts the single path + `objects` form field. Two test-semantics changes document real server behavior: `get` on a row already live in the collection returns the address only (the server omits live-row entries, so the row's data stands as last acknowledged), and `new`/`append` wire results are address strings with the child riding as its own entry (`returns_glue: true` in the fixture schemas).
- **View-fragment endpoint untouched** — `glue_view` and its template-response shape stay phase-5 until the view/component slice.

**Parallel workstream decision (2026-09-22):** `v1.1/components` (13 commits off merge-base `24b38cf`, the "split the component work from the state model" branch) implements components + template syntax against the **old** wire format. Its design docs have diverged from this branch's, it rewrites the same core files incompatibly (`callable.py`, `shortcuts/glue.py`, `declared.py`, `exceptions.py`, `test_component.py`), and it rebuilt the client bundle. Decision: finish the state-model refactor completely first, then **port** the component work onto the settled model as A5 (behavior reference, not a mechanical merge); the bundle is always rebuilt from `client_js/src`.

### A2 conformance record (pre-edit, per design/AGENTS.md)

1. **Active roadmap phase and gate.** Phase 6 (authorized 2026-09-21), slice A2 — the page-load half of the gate line "legacy-object and component E2E tests share the envelope". After A2 every Glue surface a browser meets (page load + attribute calls) speaks the same `objects` envelope; the view-fragment surface joins in the view/component slice.
2. **Governing specification sections.** state-model.md §10 "Wire format", the "Page load" JSON (lines 1696–1728): the initial document carries `{objects: [...]}`; each entry is `address` + `policy_token` + `static_data` + `computed_data`, children are flat siblings of their owners (no nesting), and no entry carries a result tag or an `is_glue_manifest` tag. An entry is the attribute-call entry shape minus `result`/`effects`. §10 "Responses omit what did not change" applies unchanged (page load is the first snapshot, so nothing is omitted).
3. **Legacy mechanisms removed/prohibited (this slice).** The `manifest_list` outer transport for the **init context** and the `is_glue_manifest` tag on page-load entries. No compatibility envelope: the init context carries `objects` only, and the client constructor reads `objects` only. **Explicitly deferred (untouched in A2, phase-5 shapes until the view/component slice):** the `glue_view` view-fragment response (`{html, manifest_list}`), the `is_glue_template_response` result shape (its inner `manifest_list`), and multi-row query `items` result manifests — all keep the tagged `GlueManifest` shape.
4. **Mapping to the specification.**
   - `GlueObjectEntry` (new, `glue/context.py`) — §10 page-load entry.
   - `BaseGlue.entry` (new property) — the entry builder; `BaseGlue.manifest` (kept for the deferred consumers) derives from it and adds the phase-5 tag.
   - `BaseGlue._serialized_child_entries` (new) — flat entry list of the object graph; `GlueContextManager.serialized_objects` (new) serializes roots + children for the init context; `_glue_client_context` emits `objects` instead of `manifest_list`. `serialized_manifests` (kept) still serves `render_html_payload` (template responses).
   - A1 introduced entries (`process_attribute_call`) switch from tagged manifest dumps to `entry` — the spec entry is untagged; this closes the A1 residual where phase-5 tagged dumps rode as entries.
   - Client: `GlueClient` constructor consumes `context.objects`; `_loadEntries` is the shared introduce → refresh → public-register core; `loadManifests` (kept public for the view-fragment and template-response consumers) = collect tagged manifests → `_loadEntries`.
   - Test fixtures: `createEntry` (untagged) for page-load `objects`; `createManifest` (tagged) stays for the phase-5 consumer fixtures.

### A2 completion snapshot (2026-09-22)

A2 is COMPLETE and green. Gates on the current tree: 535 passed non-E2E (41 deselected), 31 passed / 10 xfailed E2E, 88 passed JS, green `js-build` (25.0 KB), ruff `-F` unchanged at the known 6-error baseline, `git diff --check` clean. Uncommitted, on top of `99d53bc`.

Implementation notes:

- `GlueObjectEntry` is the untagged wire entry; `BaseGlue.entry` builds it and `BaseGlue.manifest` now derives from it (adds the phase-5 tag). `GlueContextManager.serialized_objects` serializes roots + children as flat entries for the init context, which now emits `objects` instead of `manifest_list`. `serialized_manifests` (tagged) is retained for `render_html_payload` (template responses) only.
- **Behavioral preservation:** `GlueClient.resolveManifest` still introduces without registering a public name (it calls `_introduceEntries`, not `_loadEntries`); only page load and `loadManifests` register public names. `_registerPublicEntry` (renamed from `_registerPublicManifest`) is the shared registration core.
- A1 introduced entries now ride untagged (closes the A1 residual where phase-5 tagged dumps rode as entries); the JS `introduce` path is tag-agnostic so no client change was needed for that.
- JS test fixtures: constructor contexts moved to `objects: [createEntry(...)]`; introduced-entry fixtures (the `new` draft, `append` form) use `createEntry`; multi-row query `items` and the deferred view-fragment / template-response `manifest_list` fixtures keep `createManifest` (tagged).

### A3 prerequisite: policy-token lifetime — DECIDED (2026-09-22, ADR 013)

**24 hours from issuance** (`DJANGO_GLUE_PROXY_POLICY_MAX_AGE_SECONDS = 86400`), fixed, successor-issued only when retained values change. Recorded in `design/reactive-system/decisions/013-policy-token-lifetime.md`; roadmap checklist item closed; `settings.py` and `AGENTS.md` now state the semantics (the old "rolling" wording is corrected). Rationale in one line: the token is session-bound and re-authorized per request, so the lifetime bounds only the accepted replay/staleness residual — and roots have no reintroduction path, so a shorter default would make long-open pages reload and discard in-progress root-level edits. User may veto; changing the number is a one-line edit.

### A3 conformance record (pre-edit, per design/AGENTS.md)

1. **Active roadmap phase and gate.** Phase 6, slice A3 (reintroduction protocol). Gate contributions: the open constraint "Verify child reintroduction after expiry preserves the proxy, editable draft, Alpine scope, and request queue at the same canonical path", and the §10 row-4 slot-resolution state ("Live but listed in the request's `reintroduce` | yes | yes, reintroduced | same address").
2. **Governing spec sections.** state-model.md §10: "Reintroducing an expired child" (the request entry carries an optional client-supplied `reintroduce` list of canonical child paths — the spec's own example is a call-less entry; untrusted unsigned input; a path that is not a declared slot fails admission; the address is unchanged; the factory runs and the result is authorized from scratch; client-side, `policy_expired` marks the address stale rather than disposed; the proxy rejects further calls with a recoverable error that names its owner; a page root has no reintroduction path — an expired root is a reload); "What 'newly introduced' means" (slot-resolution table row 4); "Failure is per-address" (protocol admission failure is an address fault). ADR 013 supplies the known expiry.
3. **Legacy mechanisms removed/prohibited.** None removed; A3 is additive.
4. **Mapping.**
   - Server: `AddressedObjectEntry.call` becomes optional (`AttributeCall | None`) with a new `reintroduce: list[str]` (the spec example omits `call`); an entry with neither is malformed (envelope fault). `AttributeCallRequestContext.reintroduce` carries the list. `BaseGlue.process_attribute_call` admits the paths against declared child slots (CHILD-kind definition paths) — an undeclared path raises `invalid_reintroduce` (new closed code; a protocol admission failure, i.e. a per-address error entry), then binds children with `live_children=policy.children, reintroduce=...` (the `GlueChildBinder` already implements row-2 carry-forward and row-4 same-address reintroduction — the wiring is the gap: `_bound_children` never received the live set). A call-less entry produces an addressed entry with `result: None`, empty effects, and omitted-when-unchanged token/static/computed, plus the reintroduced children. Reintroduced children ride in `introduced` at their unchanged address even when the `children` map is otherwise unchanged.
   - Client: `sendAttributeRequest` gains optional `reintroduce` / optional `attribute`; the JS child binder records `parent = {address, path}` on each child record; `GlueAddressRecord` gains `stale` state (cleared when a fresh policy token is applied); `_callAttribute` on a `policy_expired` target error marks the record stale, issues the owner repair request (`reintroduce: [path]`), and — if the repaired entry reintroduces the child — retries the original call exactly once (the spec-permitted "default client behaviour"); on repair failure it propagates the `policy_expired` `GlueAddressError` carrying the owner so composition code can repair manually; while stale, further calls reject immediately with the recoverable error naming the owner.
5. **Scope boundary (recorded decision).** A3 reintroduces **fixed child slots** (CHILD attributes) on any owner, including collection rows (a row is a `ModelGlue` and uses the base binder). **Collection item keys are not reintroducible in A3** — a key path is not a declared slot, so admission rejects it (`invalid_reintroduce`). Keyed-collection reintroduction (and the row-2 "factory does not run" optimization for live collection items, which `BaseCollectionGlue._bind_children` currently does not do) is a recorded follow-up, not A3.

### A3 completion snapshot (2026-09-22)

A3 is COMPLETE and green. Gates on the current tree: 542 passed non-E2E (41 deselected), 31 passed / 10 xfailed E2E, 94 passed JS, green `js-build` (25.4 KB), ruff `-F` at the known 6-error baseline, `git diff --check` clean. Uncommitted, on top of `99d53bc`.

Implementation notes:

- **Server:** `AddressedObjectEntry.call` is now optional with a `reintroduce: list[str]`; an entry with neither is a malformed-request envelope fault. `BaseGlue.process_attribute_call` admits `reintroduce` against declared CHILD slots (`_admit_reintroduce`, new `invalid_reintroduce` closed code) and binds children against the incoming live set **after the call runs** — binding before the call would freeze the child set for owners whose call adds/removes children (caught by the FormSet append test). A call-less entry returns an addressed entry with `result: None`, empty effects, and the omitted-when-unchanged token (`_reintroduce_entry`); `_introduced_entries` rides reintroduced children at their unchanged address even when the `children` map is otherwise unchanged.
- **Row 2 now holds end-to-end:** a live, non-participating, non-nullable child carries forward without running its factory on owner calls (previously the factory re-ran and a discarded token was minted on every owner interaction). Pinned by `test_live_child_carries_forward_without_running_factory_on_owner_call`.
- `BaseCollectionGlue._bind_children` and `QuerySetGlue._bind_children` accept the `live_children`/`reintroduce` parameters (contract conformance) but ignore them — keyed-item reintroduction is the recorded follow-up.
- **Client:** `sendAttributeRequest` takes optional `attribute`/`reintroduce`; the JS child binder links `parent = {address, path}` onto child records (eagerly at refresh, lazily in the property getter as fallback); `GlueAddressRecord` carries `parent`/`stale` (stale clears when a fresh token is applied). `_callAttribute` was restructured into `_attempt` (stale rejection + one `policy_expired` recovery) and `_singleCall` (the old body). `_reintroduceWithOwner` marks the record stale, sends the owner a call-less `reintroduce: [path]` request, applies the owner + reintroduced entries, and lets `_attempt` retry the original call exactly once; on failure the `GlueAddressError` carries `owner = {name, address}`. While stale, calls reject immediately with the recoverable error naming the owner. An expired root (no `parent`) is not repaired and reports `owner: null`.
- **Tests:** 7 new Python tests in `test_component.py` (call-less reintroduce at the existing address with a fresh token, admission fault + factory-not-run, call+reintroduce together, row-2 carry-forward through the full call path, malformed entry, call-less parse, batch independence of `invalid_reintroduce`); 6 new JS tests in `tests/reintroduction.test.js` (parent link, transparent repair+retry, failed-repair recoverable error naming the owner, stale rejection without a round trip, in-progress work surviving reintroduction and resending on the retry, expired root with no owner).
- **Test-fidelity notes (mocks must stay honest):** a reintroduced child entry is a full entry (it carries `static_data`; the client `introduce` replaces static data, it does not merge). The repair token in a mock must differ from the page-load token (same policy payload + same `created_at` produces the same token string).

### A4 conformance record (pre-edit, per design/AGENTS.md)

1. **Active roadmap phase and gate.** Phase 6, slice A4 (disposal + effects completion). Gate contributions from the phase-6 gate line and its checklist: "replacement/removal disposal passes" (a different address at a path is a replacement; an absent nullable path is a removal; the same path with the same address preserves proxy, editable draft, Alpine scope, and request queue); the transient-result checklist item — repeated calls must not grow the owner's token, client-side disposal of a result must leave no reference a later owner response can trip over, owner disposal cascades to produced results, and `effects.dispose` tears one down on demand; disposal follows lifecycle ownership recursively.
2. **Governing spec sections.** state-model.md §6 (effects are a separate channel: "Address disposal is also an effect. A response may include `effects.dispose` for the responding address itself or addresses it owns when a nonvisual object is authoritatively removed... applied after the relevant state reconciliation and DOM morph, recursively tears down client-owned descendants, and never returns to the server as state"; the wire example places `messages`/`redirect`/`events`/`dispose` under `effects`); §10 staged client operation (step 6 "bind canonical child paths... and mark displaced children", step 7 "resolv(e) callable-result address references, recording the producing address as each transient result's lifecycle owner", step 9 "dispose displaced children and explicit disposal effects, recursively following lifecycle ownership", step 10 "deliver remaining effects"); §10 "What 'newly introduced' means" (the replacement/removal paragraph: "The same path with the same address preserves the existing proxy, editable draft, Alpine scope, and request queue. A different address at that path is a replacement; an absent nullable path is a removal"); §10 "Callable capability and server injection" + the transient-result subsection (transient results are not in the signed `children` map; "its lifecycle ownership is client registry bookkeeping... the client records the producing address when it registers the introduced entry, and that record is what drives recursive disposal"; "callable results instead receive fresh opaque transient keys, so repeated calls introduce distinct children"; "owner disposal cascades to it [via] the client registry's recorded producer, which is also what cancels its queued calls and rejects late responses"; "`effects.dispose` is the replacement" for tearing down transients); §8 "Address separator scheme" (four fixed roles: `#`, `.`, `[ ]`, `:`); §4 "Hard composition boundary" (lifecycle ownership: "Every live address has exactly one lifecycle owner... Parentage controls lookup and disposal, not state ownership"). component-system.md §Lifecycle (lines ~897–931): an address is disposed when its owner authoritatively removes it from a keyed collection or successor `children` map, an `effects.dispose` entry removes a nonvisual object, or the page unloads; "Each client registry entry carries a local, monotonically increasing generation... Its response entry is applied only if that exact generation is still active. Disposal cancels queued calls, aborts a single-address in-flight request where possible... response entries for disposed generations are discarded individually. Existing references to the disposed proxy become tombstones and reject later calls. Reintroducing the same canonical address creates a new proxy generation." ADR 013 (fixed token lifetime) underpins "late response" discard semantics.
3. **Legacy mechanisms removed/prohibited.** `GlueRedirectResponse`'s legacy shape — redirect under `result: {redirect: {url}}` — contradicts the §10 wire example (redirect under `effects`); it is replaced by a `GlueResponse.redirect` field surfaced as `effects.redirect`. No other legacy mechanism is reused: there is no existing dispose infrastructure anywhere in the tree (verified by search).
4. **Mapping.**
   - **Server.** `address.transient(owner_address)` (address.py): mints `owner["t<16 hex>"]` — the spec's "fresh opaque transient key" beneath the producer, expressed with the existing keyed-item `[ ]` role and the string-quoting rule (no new separator role is added; the scheme table is fixed). `BaseGlue.dispose()` + `_disposed` flag: the server-side declaration that the responding object is authoritatively removed (§6: dispose "for the responding address itself"); the spec fixes the effect's semantics but not the server declaration API, so a minimal marker method is the mapping decision (`ModelGlue.delete()` calls it, since the framework knows its own deletion semantics). `GlueResponse.dispose: list[str] | None` / `GlueResponse.redirect: dict | None`: owned-address disposal and the migrated redirect effect. `process_attribute_call`: a Glue-object call result that is not an already-live child is re-addressed to a fresh transient address at issuance (spec: "the address is minted from the owner address and an opaque transient key at issuance"); the entry's `effects` gains `redirect` (when set) and `dispose` (when non-empty, otherwise omitted — omission stands with the §10 omit-what-did-not-change discipline); dispose addresses are validated against the responding address + successor `children` values + this response's introduced entries, a violation raising the new closed code `invalid_dispose` (an address fault → per-entry error, per "Failure is per address").
   - **Client.** `GlueAddressRecord`: A3's `parent` generalizes to `owner = {address, path}` with `path: null` for transient producers (the spec's single "lifecycle owner" concept covers both); `disposed` tombstone flag; `generation` (existing inert field) now participates — captured in `captureRequest()`, incremented on a stale reintroduction (spec: "Reintroducing the same canonical address creates a new proxy generation") and on disposal; `reconcile` discards an entry whose captured generation no longer matches ("response entries for disposed generations are discarded individually"); `boundChildren` records the last-bound `{path: address}` map. `GlueChildBinder`: on each owner refresh, diffs the previous bound map against the successor `children` map — a changed or absent address marks the old child displaced (the spec's step 6), sets `owner` links on live children, and the displaced set is flushed through `registry.dispose` after binding (step 9, after state reconciliation; no DOM morph exists for nonvisual families). `GlueAddressRegistry.dispose(address)`: recursively collects the owned set (BFS over `record.owner.address` — "recursively following lifecycle ownership"), tombstones each record, runs the optional `proxy._onDispose()` cleanup hook (components will supply their DOM/Alpine cleanup in A5), and removes entries from the registry. `BaseGlueProxy`: `_attempt` rejects on a tombstoned record first (code `disposed`); `_singleCall` discards a whole response when its own generation is gone (disposed or disposed-and-reintroduced — the record object was replaced); `_convertResult`-time bookkeeping records the producing address as each transient result's lifecycle owner (step 7) without overwriting an existing owner ("one live address cannot be introduced under two owners"); `_processEffects` applies `effects.dispose` (step 9, before message delivery at step 10) and `effects.redirect` (browser navigation); public `$dispose()` — the spec's "explicitly dispose it when that scope closes" (component-system.md ~982), name not fixed by the spec, following the existing `$`-prefix convention.
5. **Scope boundary (recorded decisions).**
   - **`$dispose()` is permitted only where client-side disposal cannot dangle a signed reference:** page roots (no owner) and transient results (`owner.path === null` — never in a signed `children` map, so a later owner response cannot reference them, which is exactly the spec's "leaves nothing dangling"). A slot-bound child (`owner.path !== null`) is refused: it is signed in its owner's `children` map, so a client-side removal would make the owner's next response fail the staged-apply requirement that every referenced child be live or introduced. Owners remove children via a successor `children` map, `effects.dispose`, or by being disposed themselves.
   - **`effects.events` (declared semantic events) and the universal `$on()` API are out of A4** — the server has no event declaration mechanism yet (it arrives with the component workstream in A5); the client `_processEffects` ignores the key for now. The legacy three-event `before/after/error` listener system is not touched in A4 (its replacement is the A5 events contract; the audit ruling deprecates-first still applies).
   - **Transient-result capability capping at issuance is not implemented in A4** (spec: "Enforced at issuance, baked into the child's signed policy"). The minted result keeps its own configured access; recorded as a security follow-up for the user to prioritize.
   - **`$refresh()`** (§6: "remains an ordinary addressed request", the polling primitive) has no counterpart in this tree; recorded, not implemented in A4.
   - **Network abort on disposal** ("aborts a single-address in-flight request where possible") is not plumbed; the generation guard is the correctness mechanism the spec names for late responses, and queued calls are cancelled by rejecting against the tombstone. Recorded.
   - **Component morph disposal** (root removed during a morph) is A5; A4's flush point (after bind, before effects) is the nonvisual equivalent of "after the relevant state reconciliation and DOM morph".
    - **Ownership transfers with the successor map (recorded interpretation).** When an owner's successor `children` map replaces a child at a path and the replacement child references a grandchild that the displaced child also referenced, the grandchild is **not** disposed by the displaced child's teardown: the displacement flush runs after the replacement's introduce has re-linked the shared grandchild to the live successor, so the recursive traversal no longer sees it as owned by the doomed address. The successor relationship map is authoritative (state-model.md §10: "still making the owner's successor relationship map authoritative"), and the server side agrees — `_serialized_child_entries` recursively re-sends such grandchildren when the owner's children map changes. A child referenced only by the displaced owner is still disposed recursively.

### A4 completion snapshot (2026-09-22)

A4 (disposal + effects) is complete and green. Implementation as mapped in the conformance record: server — `address.transient()`, `BaseGlue.dispose()` + `_disposed`, `GlueResponse.dispose`/`redirect`, `process_attribute_call` transient minting + effects construction/validation (`invalid_dispose`), `GlueRedirectResponse` migrated, `ModelGlue.delete()` emits disposal (9 tests in `django_glue/tests/glue/test_disposal.py`); client — `owner = {address, path}` record model with tombstone + generation capture/guard, child-binder displacement diff, registry recursive `dispose`, `_attempt` tombstone rejection + stale marking, `_singleCall` discard, transient-result ownership, `$dispose()`, `_processEffects` dispose/redirect (15 tests in `client_js/tests/disposal.test.js`). New E2E: `test_detail_model_delete_disposes_proxy` (delete through the detail page; asserts tombstone, registry tombstone state, and the DB row gone).

**Mid-slice finding 1 — tombstones stay in the registry (implementation correction).** The first implementation removed disposed records from the registry. That broke the list page: when a collection window changes (filter/orderBy/slice), the displacement flush disposes the outgoing rows and their children synchronously, but Alpine's queued row effects re-run afterward and read `gorilla.skills` — with the record deleted, the child getter returned `null` and the template crashed (`Cannot read properties of null (reading 'items')`). component-system.md's tombstone language ("Existing references to the disposed proxy become tombstones") supports retention: `registry.dispose` now tombstones records (flag + generation bump + `proxy._onDispose()`) without deleting them; `record.introduce` revives a disposed record (clears the flag, bumps the generation, resets the queue) so a re-introduced address resumes at the same record/proxy. Consequences: a path removed from the successor map reads `null` (no address to resolve) while the tombstone itself remains; namespace access after root disposal returns the tombstone proxy, not `null`. Because revival can outlive an in-flight call, `_singleCall`'s discard condition now also compares `requestCapture.generation !== this._record.generation` — a response for a disposed-then-revived generation is discarded wholesale, result included (pre-revival, the `disposed` flag alone caught it). Follow-up: tombstone garbage collection (the registry accumulates disposed records for the session's life; lightweight, but unbounded).

**Mid-slice finding 2 — M2M fields were missing from the default model field projection (pre-existing gap, fixed).** The A4 E2E target (the detail page, the only E2E page with a deletable model proxy) crashed on plain load: `x-for="choice in gorilla.$fields.skills.choices"` found no `skills` field. Three server gaps: `_default_field_names` in `model_fields.py` listed concrete fields only (M2M excluded from the `exclude`/`__all__` default path); `ModelFieldAdapter.schema()`/`computed_data()` guarded on `field.concrete`, which is never true for M2M, so the `choice_model_path`/`pk_field` enrichment (which the client needs to build `ManyRelationFieldGlue`) was dead code for them; and `_is_concrete_editable_field` rejected M2M, contradicting `_apply_m2m_state`/`save()`/`_stage_model_attribute_value`, which already treat M2M as an editable value (the detail template's `skills` input proves the intended semantics). Fixed all three: M2M names join the default list, the concrete guard is dropped (the `is_relation`/`related_model` guards already scope the enrichment), and M2M is editable by default. `test_objects.py` updated (`skills` is now a `ManyToManyField` value attribute; new `test_many_to_many_is_an_editable_identity_value`).

**Gate results (all rerun 2026-09-22):** `just test` 552 passed, 42 deselected; `just js-tests` 109 passed, 0 failed; `just js-build` green (25.9 KB); `just test-e2e -x -q` 32 passed, 10 xfailed, 552 deselected; `ruff check --select F` — no findings in any touched file (repo-wide baseline findings in untouched files unchanged); `git diff --check` clean.

**Follow-ups (not A4):** tombstone GC; transient capability capping at issuance (security); `effects.events` + `$on()` (A5); `$refresh()`; network abort on disposal; component morph disposal (A5); keyed-collection item reintroduction (A3 follow-up).

### A1–A4 review correction conformance record (pre-edit, 2026-09-22)

1. **Phase and gate.** Phase 6 A1–A4 review correction, before commit. The phase 6 batch gate requires every independently addressed entry to advance as it would alone; A5 remains unstarted.
2. **Governing contract.** `state-model.md` §10, “Failure is per address, not per request” and the flat `objects` envelope: a batch is strictly independent, a child gets a response entry when it independently participates, and a response has one token/computed-data pair per address.
3. **Legacy mechanism removed.** The resolver's first-seen response de-duplication currently lets an owner's introduced child entry suppress that child's independently requested entry. Keep one entry per address while giving the independently requested entry precedence over incidental introduction.
4. **Mapping.** `GlueAttributeCallResolver._resolve_json_response_from_context` reserves request addresses before appending introduced entries. A regression test batches an owner reintroduction and a child call and checks that the child's call result survives. No new public field, class, or method is needed.

**Review correction result.** The new batch regression failed before the resolver change and passes after it. Independently requested entries now take precedence when an owner also introduces their address; incidental introduced entries remain de-duplicated. The five new code comments identified in review were removed and the single-use `_disposedError()` helper was inlined. Gates rerun 2026-09-22: `just test` 553 passed, 42 deselected; `just js-tests` 109 passed; `just js-build` green (25.9 KB); `just test-e2e -x -q` 32 passed, 10 xfailed, 553 deselected; Ruff `--select F` reports only the six pre-existing untouched-file findings; `git diff --check` clean.

## Implementation-check results

From the previous handoff's "implementation checks that still need attention":

1. **ModelFieldAdapter attaches only to value definitions** — verified. Adapters are attached in `BaseGlue._collect_attributes` only when `definition.kind == GlueAttributeKind.VALUE` (base.py:138). Projected relation children are separate CHILD-kind declarations with no adapter; their raw identity/membership leaves are distinct VALUE definitions.
2. **Editable `<relation>_ids` staging through ModelGlue** — verified after the hydration cutover (see below). Editable values stage into `_editable_draft` through the attribute pipeline and apply to the instance from the draft; M2M membership applies from the draft in `save()`.
3. **FormFieldAdapter state matches `BoundField.value()`, no model/QuerySet leaks** — verified. The adapter is a leaf adapter for schema and computed data only; state flows through the field getter (`FormGlue._get_form_attribute_value` → `BoundField.value()`). The two regression tests in `test_objects.py` (`test_form_field_get_reduces_model_choice_initial_to_pk`, `test_form_field_get_falls_back_to_field_initial`) pass.
4. **QuerySet collection metadata stays collection-scoped** — verified. `QuerySetGlue` does not override `get_attribute_adapters` (default `{}`, base.py:170); rows are addressed `ModelGlue` children (queryset.py:420) that carry their own field schemas.
5. **Remove `BoundGlueAttribute.metadata`** — resolved in (4b); the metadata property stack and transitional response/manifest shapes are removed.

## Findings for phase 4 (recorded 2026-09-18 — do not lose)

### ModelGlue's legacy hydration path — RESOLVED (see "ModelGlue hydration cutover" below)

The legacy direct-setattr override is removed; hydration now runs through the attribute pipeline into `_editable_draft`, with the draft applied to the instance per state-model.md §4. Two facts from that investigation still matter:

- **Residual hazard — RESOLVED in (4c):** admitted update values and signed snapshots are now converted through the serializer registry before hydration. Numeric strings reach the ModelGlue instance as the field's Python type, and the stale `delete()` hazard comment is removed.
- **Per-callable state-ingestion flags are removed by the design, not enforced:** `state-model.md` §9 lists `takes_client_state` and `updates_client_state` under "Deleted", and §5's client-computed `updates` diff (`diff(canonical, ephemeral)`) is the replacement mechanism. Today the flags are declared on `DeclaredAttribute`/`DeclaredAttributeOptions` but **inert** — the collector drops them and `_load_client_state` runs unconditionally in `process_attribute_call`; the unmigrated JS client still sends editable state with every call (client_js/src/proxies/base.js:84). (The old hardcoded `takes_client_state: True` callable-metadata line was removed in (4b) with `_get_attribute_metadata`.) Remove the flags with the phase-5 client migration. **(Done in phase 5 — see the continuation snapshot.)**
- ~~`FormGlue` hydrates by rebinding the Django form from client data — a separate legacy path phase 4 should normalize to the draft contract.~~ **RESOLVED in (4a):** FormGlue now stages through the attribute pipeline into `_editable_draft` and rebinds the form from the draft (see the (4a) implementation notes). `FormSetGlue` still delegates per keyed child with the legacy keyed container shape — that is §8 collection work, not a hydration bypass.

## Outstanding FormSet behavior (not the immediate task)

- Enforce `min_num` and `max_num` in `validate()` and `append()`.
- Add a remove operation.
- Make `can_delete` affect behavior rather than merely being signed identity.

## Next actions

### 1. Phase 5 — COMPLETE (2026-09-21)

The phase-5 migration of `client_js/src` to the settled `state_snapshot` + `static_data` + `computed_data` + `updates` contract and role-aware reconciliation is implemented and all three review targets are resolved (see the continuation snapshot's "Review target resolutions"). Every mandatory gate is green on the current tree (rerun 2026-09-21): 527 passed non-E2E, 31 passed / 10 xfailed E2E, 88 passed JS, green build, clean ruff baseline. The work is uncommitted on top of baseline `44803c0` and ready for review/commit; do not start phase 6.

The inert `takes_client_state` / `updates_client_state` declaration options were already removed in this phase-5 work; `LoadingStrategy` remains (its removal was explicitly out of this slice).

### 2. Phase 6 — A1 + A2 + A3 + A4 COMPLETE (2026-09-22), next is A5

A1 (attribute-call `objects` envelope), A2 (page-load `objects` envelope), A3 (reintroduction protocol; lifetime prerequisite settled as ADR 013 — 24 h from issuance), and A4 (disposal + effects — see the A4 completion snapshot: tombstone retention + revival, generation-stale discard in `_singleCall`, the M2M default-projection fix, and the detail-page delete E2E) are done and green. Every surface a browser meets (page load + attribute calls) speaks the shared `objects` envelope, an expired child is repairable through its owner at the same canonical address, and disposed objects leave inert tombstones whose late responses are discarded by generation guard; only the `glue_view` fragment, template-response results, and multi-row query `items` remain on the tagged `manifest_list` phase-5 shape (deferred to the view/component slice). Next is **A5: component port from `v1.1/components` + consumer migration + `docs/` rewrite** (this is also where `effects.events`/`$on()`, component morph disposal, and custom `Component` registration in `glue_class_registry` land). Recorded follow-ups: tombstone GC, transient capability capping at issuance, `$refresh()`, network abort on disposal, keyed-collection item reintroduction and the row-2 factory-skip for live collection items.

The reviewed A1–A4 increment is committed. Its review correction and gate results are recorded above. The only remaining untracked file at commit time is `client_js/dbg_tmp.mjs`, a local debugging script excluded from the commit.

### 3. Outstanding collection behavior (later)

The FormSet cardinality/removal items remain recorded above.

## Most relevant files

Core state model:

- `django_glue/serialization.py`
- `django_glue/glue/base.py`
- `django_glue/glue/policy.py`
- `django_glue/glue/children.py`
- `django_glue/glue/collection.py`
- `django_glue/glue/attributes/definition.py`
- `django_glue/glue/attributes/registry.py`
- `django_glue/glue/attributes/collector.py`
- `django_glue/glue/attributes/adapter.py`
- `django_glue/glue/attributes/declared.py`
- `django_glue/exceptions.py` (`GlueCalledNonCallableAttributeError`)

Django families:

- `django_glue/glue/objects/django/field_adapter.py`
- `django_glue/glue/objects/django/model/object.py` (draft-based hydration: `_load_client_state` → `_apply_draft_to_instance`/`_apply_file_fields`; `save()` → `_apply_m2m_state`/`_rebase_draft`)
- `django_glue/glue/objects/django/form/object.py` (note the form-rebind `_load_client_state`)
- `django_glue/glue/objects/django/formset.py`
- `django_glue/glue/objects/django/queryset.py`
- `django_glue/glue/sequence.py`

Client runtime (phase 5):

- `client_js/src/runtime/state.js`
- `client_js/src/runtime/addressRecord.js`
- `client_js/src/runtime/addressRegistry.js`
- `client_js/src/runtime/attributeMaterializer.js`
- `client_js/src/runtime/childBinder.js`
- `client_js/src/runtime/responseDispatcher.js`
- `client_js/src/proxies/base.js` (family proxies are facades over the registry)
- `client_js/tests/state_model.test.js`, `client_js/tests/family_api.test.js` (new phase-5 suites)

Focused tests:

- `django_glue/tests/glue/test_update_admission.py`
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

## A5 handoff — 2026-09-22, interrupted for agent transfer

The user authorized A5, then corrected the stamp syntax: **use the current
component branch in `./django-glue` (`e6f204b`) as the source for the Django
`{% glue_component %}` templatetag. Do not implement `<glue:... />` elements or
a custom `DjangoTemplates` compiler.** The component branch targets the old
manifest wire, so port behavior onto this branch's addressed `objects` wire;
do not merge it mechanically. The old syntax remains inside a collapsed
historical section of `component-system.md`; the active section, `design.md`,
and `roadmap.md` now specify the tag. `design/components/spec.md` exists in
the `./django-glue` worktree, not in this worktree.

Current uncommitted A5 edits cover:

- `glue_view`, template-response results, queryset multi-row results, and
  sequences moved toward `{html, objects}` and address-only item references;
  Python and JS tests were updated for those surfaces.
- Component registration, typed declared parameters, signed reconstruction,
  mount on introduction, recursive component module discovery, collision
  checking, stable typed keys, `{% glue_component %}`, one-root injection,
  and per-root addressed entry data for pages whose Glue init renders before
  component content. Stamped components are excluded from global client names.
- Client DOM lookup (`Glue.from(element)`, `$glue`, `component.$el`), address-keyed
  morphs, removal disposal, and a component render path that morphs before
  delivering `effects.events`.
- `Glue.event()` and source-scoped `$on()` with a bubbling component DOM event;
  the old `addListener`/`removeListener` runtime API was removed. A new
  component guide and event guide were written; legacy event sections in five
  family guides now point to the new guide.
- A `CounterDashboard`/`CounterCard` browser fixture and E2E test demonstrate
  typed keyed tags, independent state, event delivery, parent morph, disposal,
  and identity preservation.

Verified after these edits: `just test` **557 passed, 43 deselected**;
`just js-tests` **111 passed**; `just js-build` green (26.4 KB);
`just test-e2e django_glue/tests/e2e/test_component_page.py -q` **1 passed**;
`.venv/bin/python manage.py check` green; `git diff --check` clean. A later
full `just test-e2e -q` was **interrupted by the user** for this handoff, so
the full E2E gate is unknown. `just docs` failed only because mkdocstrings
could not fetch Python's inventory under network restriction. The broad Ruff
check reported pre-existing and new style findings; run focused Ruff on new
files, fix substantive findings, and distinguish baseline findings.

**Full E2E resumed (2026-09-22, next session).** The interrupted full run was
red: 14 errors + 1 failure, all from `test_project` templates still calling the
removed `addListener` API (the E2E JavaScript error guard fails every test on
those pages). Migrated those consumers to call-site promise handling per the
event guide ("Loading and transport errors remain normal promise behavior"):
`gorilla/page/{detail_page,detail_page_partial,list_page}.html`,
`fight/page/list_page.html`, `gorilla/component/gorilla_form_modal.html`. The
fight list's listeners were attached to the queryset proxy while the buttons
act on rows, so they never fired; their notifications now sit on the row
save/delete handlers. No built-in `saved` event was added (component-system.md
permits one, it is not required; open question). Full `just test-e2e -q`:
**33 passed, 10 xfailed**. Do not run `just test` concurrently with E2E — they
share the test database and produce spurious setup errors.

**Legacy manifest removal conformance record (pre-edit, 2026-09-22).**

1. *Phase and gate.* Phase 6 A5, gate line "legacy-object and component E2E
   tests share the envelope" — no surface may still speak the tagged shape.
2. *Governing sections.* state-model.md §10 "Wire format" (page load and
   attribute calls carry `{objects: [...]}`; "no entry carries a result tag or
   an `is_glue_manifest` tag"; a Glue-returning callable's wire `result` is the
   address); roadmap.md "There is no compatibility envelope".
3. *Legacy removed.* `GlueManifest`, `BaseGlue.manifest`,
   `BaseGlue._serialized_child_manifests`, `GlueContextManager.serialized_manifests`,
   `GlueResponse._serialize_glue_values`/`_serialize_result` (the result path
   now lives in `process_attribute_call`; `to_json_response` only serves
   envelope-fault errors), client `loadManifests`/`resolveManifest`/
   `_collectManifests`, and the `is_glue_manifest`/`is_glue_template_response`
   branches of `_convertResult` (no server path emits either).
4. *Mapping.* No new field, class, or public method. `GlueClient.loadObjects`
   absorbs the single-caller `_loadEntries`/`_introduceEntries`. Tests move to
   `BaseGlue.entry`; nested-Glue result rejection is tested through
   `process_attribute_call` instead of the removed serializer; assertions whose
   only purpose was that the tag is absent are dropped (design/AGENTS.md: no
   historical tests).

*Result.* Done as mapped (plus `test_model_related_state.py` moved to
`_serialized_child_entries`, `sequence.py` and `addressRegistry.js` messages
say "entry"). Gates: `just test` 555 passed (four legacy serializer tests
removed, one parametrized call-path rejection test added), `just js-tests` 111
passed, `just js-build` 26.2 KB, `just test-e2e -q` 33 passed / 10 xfailed.
Item 2 below is complete.

**Component contract audit (2026-09-22).** Done without a decision (the spec
settles them): the component class now has a `__signature__` generated from its
declared parameters (skipped for classes that still hand-write `__init__`);
`event.py`'s DOM collision list is now the WHATWG HTML global event handlers
plus the UI Events, Pointer, Touch, CSS animation/transition, and window
lifecycle events (component-system.md: "a published list").

**User decision — list adaptation (2026-09-22).** `SequenceAdapter` wraps a list
into a `SequenceGlue` only when the list's items are meant to be proxies: it
holds `BaseGlue` objects, or its declaration names a `glue_factory` that turns
raw items (model instances, forms) into them. Any other list stays plain data;
a mixed Glue/raw list with no factory still raises. This narrows the audit's
`glue_factory` "REPLACE" and `value_adapters` "COLLAPSE" rulings: the adapter
and `glue_factory` stay. The design text (state-model.md's hard composition
boundary routes and the audit table) must record this in the docs pass. The
`CounterDashboard` `value_adapters=[]` workaround is gone.

**User decision — one introduction step (2026-09-22), conformance record.**

1. *Phase and gate.* Phase 6 A5, component half of the gate.
2. *Governing sections.* component-system.md §4 "Mount" (`mount()` is the single
   initial-introduction hook, called after parameters/defaults and request
   binding, before the first policy token and initial HTML; not on
   reconstruction or token advance); state-model.md §4 hard composition
   boundary (four introduction routes); the user's Liskov rule (no subtype
   branching in the general layer, no no-op base members).
3. *Legacy removed.* The `isinstance(glue, Component)` mount branches in
   `GlueContextManager.add_glue` and `GlueChildBinder`.
4. *Mapping.* `BaseGlue.introduce(request)` — binds the request and requires
   `INTRODUCE` authorization (raises `GlueAuthorizationError`); true of every
   family. `Component.introduce` extends it with `mount()`. Callers: page roots
   (`add_glue`, denial raises), child slots (`GlueChildBinder`, denial omits
   the child), callable results (`process_attribute_call`, denial is the
   entry's `not_authorized` fault). The last closes a gap: a component
   returned as a transient result was never mounted or authorized for
   introduction.

*Result.* Done as mapped. `introduce()` authorizes against the given request
and binds only when authorized, so a denied child stays unbound. New test:
`test_component_returned_from_a_callable_is_mounted_at_introduction`. Gates:
`just test` 562 passed, `just test-e2e -q` 33 passed / 10 xfailed.

**Spec gap audit (2026-09-22) — implement ALL of these before the `docs/`
rewrite.** The user ruled that docs describe the finished contract, so every
spec requirement lands first. Design-doc edits already made in this session
(component-system.md, state-model.md, design.md, roadmap.md) record decisions
and stay; the partial `docs/api/glue/shortcuts.md` edit is on hold until the
gaps close. Sources: state-model.md "Consequences", roadmap.md "Open
implementation constraints", ADR statuses (headers are stale; each was checked
against code), the component workstream spec's deferrals.

A. Spec-mandated removals still in code:
1. `TemplateGlue`, `Glue.template()`, `initial_context_data`, the client template
   proxy/namespace, their tests, fixtures, and nav entries.
2. `Glue.sequence()` entrypoint (the `SequenceGlue` class stays; list adaptation
   per the user decision above).
3. `LoadingStrategy.INHERIT`.
4. `identity=` (`Glue.property(identity=...)` and remaining `identity=True` sites).
   *A2–A4 done (2026-09-22):* `Glue.sequence()` removed (its registration test
   now uses `Glue.object(request, SequenceGlue(...))`); `LoadingStrategy.INHERIT`
   and the single-purpose `resolved_loading_strategy` removed; `identity=` removed
   from `Glue.attr`/`Glue.property`, `DeclaredAttributeOptions`, the definition,
   and the collector — `BaseGlue.get_identity()` defaults to `{}` (custom objects
   sign reconstructors through `_retained_state`), and `_GluePropertyDescriptor`
   lost its `__call__`/`_bind` (only the removed `identity=` form used them).
5. `related_field_config` → nested `fields`/`exclude` relation paths, optional
   `Glue.fields()` sugar, and a separate `choices` mapping for relation choice
   sources (state-model.md "Consequences"; roadmap constraint "Normalize ordinary
   nested field-path lists…").
   *A5 conformance record (pre-edit, 2026-09-22).* (1) Phase 6 gap closure.
   (2) state-model.md §9 "`ModelGlue` and `QuerySetGlue` use one explicit
   field-projection graph" through "Configuring `Glue.choices(...)` opts into the
   server-side path" (lines ~1370–1524), Consequences "`related_field_config` is
   removed", §10 "The same path carries choice-source continuations".
   (3) Removed: `related_field_config` and its `RelatedFieldConfig` /
   `NormalizedRelatedFieldConfig` / `RelatedFieldPolicyConfig` shapes. Its
   per-relation `fields`/`exclude` are already dead (projection comes from nested
   `fields` paths via `_projected_relations`); only `choice_queryset` is live.
   (4) Mapping: `choices: Mapping[str, QuerySet]` on `ModelGlue`, `QuerySetGlue`
   (forwarded to rows), and the `Glue.model`/`Glue.queryset` shortcuts — each key
   must name an exposed relation (an included field or projected relation) and
   query its related model; signed as encoded querysets decoded through
   `unpickle_query`. Implicit source (no `choices` entry): `{value, label}` from
   `__str__`, no server search, capped at `DEFAULT_SEARCH_LIMIT`; a related table
   over the cap raises a declaration error naming the relation and pointing to
   `Glue.choices(..., search_fields=...)` (today it loads every row, unbounded).
   `Glue.fields(*paths, **relations)`: immutable selection normalizing to the
   same canonical `a__b` path tuple, nestable, accepted by `fields` and `exclude`.
   Consumer migration outside this repo (portal `TIME_ENTRY_RELATED_FIELDS`) is
   recorded for the consumer-migration pass, not edited here.
   *A5 done (2026-09-22).* `choices=` replaces `related_field_config` on
   `ModelGlue`/`QuerySetGlue` (forwarded to rows) and the shortcuts; validation,
   signing, and allowlisted decoding live in `ModelFieldResolutionMixin`
   (`_normalize_choices`/`_serialize_choices`/`_deserialize_choices`); a key must
   name an exposed relation. Implicit sources over `DEFAULT_SEARCH_LIMIT` (25)
   rows raise `ImproperlyConfigured` naming the relation — **consumer-visible:**
   any implicit relation over a larger table now needs
   `choices={...: Glue.choices(..., search_fields=[...])}`. `Glue.fields()`
   returns the canonical path tuple (no second representation). New
   `prefetch_related` no-traversal test. Gates: 591 Python, 106 JS, 34 E2E /
   10 xfailed, `git diff --check` clean.

   *A1 done (2026-09-22):* deleted `glue/objects/django/template.py` and
   `client_js/src/proxies/template.js` (via `rm`), the `Glue.template()`
   shortcut, exports, and registry entry. The arena page (its only consumer)
   now calls a `Gorilla.rank_card` `@Glue.html_attr` that computes the rank
   server-side, so the client supplies no template context; its stale
   `this.gorilla.get()` init (pre-existing break) is removed. New E2E
   `test_arena_rank_card_renders_through_model_html_attribute`. Test fixtures that
   used the template namespace as a generic owner use their own namespaces.

6. `LoadingStrategy` (added 2026-09-22 at the user's request; ADR 002 removes
   "the existing loading-strategy state semantics"): the enum, every
   `loading_strategy` option, the entry's `loading_strategy` field, the
   `load_state` callable, `SequenceLazyLoadNotSupportedError`, and the client's
   first-access fetch (`fieldBacked._ensureLoaded`/`retryLoad`, the
   materializer and field hooks that call it, `record.loadingStrategy`,
   `base.js` `_loaded` seeding). state-model.md now says every introduced entry
   is a complete first snapshot and on-demand re-derivation is `$refresh()`.
   *Load-bearing audit (user asked that nothing load-bearing be lost):*
   - **Nested collection fan-out — load-bearing, needs a decision before
     removal.** Rows are queryset derived output (state-model.md §4 family
     table), so an eager queryset runs its query at render and ships its first
     page as signed row entries. Projected to-many relations
     (`model_fields.py` builds a `QuerySetGlue` per row) default to `LAZY`
     today, which is the only thing stopping a 100-row queryset from running
     100 relation queries at render and shipping every related row as its own
     signed entry, recursively through `_serialized_child_entries`. The spec
     does not say how collection rows avoid this once lazy loading is gone.
   - Unused querysets (search/typeahead-only registrations) pay a query at
     render instead of on first read.
   - Sequences: `LAZY` is already unusable (reconstructed sequences have no
     items); removal deletes that failure mode.
   - Models/forms: `LAZY` only withholds derived output (computed attributes,
     read-only persisted fields, adapter output); retained state is in the
     token regardless. Cost moves to render time.
   - Client: `queryset.js` `_loaded` doubles as "this query has run" for
     `all()`/`refresh()` caching, seeded from the strategy in `base.js`.
   - Components and formsets already default to `EAGER`.
   *User decision (2026-09-22): option (a).* Every object introduces complete;
   a queryset introduces no rows and rows answer its query callables
   (state-model.md §10). Consumer audit: one explicit `loading_strategy`
   (portal `time_entry_day.py:146`, `EAGER` — satisfied by the new default), 55
   `Glue.queryset` registrations all on default `LAZY` (unchanged under (a)),
   `computed_attributes` only on querysets. Queryset `preload` is a deferred
   roadmap extension. A6 implementation must:
   - drop rows from `QuerySetGlue.get_computed_data(include_all=True)` and
     rewrite the tests asserting eager queryset rows at introduction;
   - make the client queryset proxy start unqueried at introduction instead of
     seeding `_loaded` from the strategy (`base.js`); cover with E2E;
   - migrate spire showcase `load_state()` calls (`live_model_card.html`,
     `form.html`, the showcase E2E, `knowledge` form-view test) and the portal
     `scope_of_work` test to `$refresh()`, and the portal deal E2E that awaits
     `deal._loadPromise`;
   - depends on B7 (`load_state` is removed only once `$refresh()` exists).
   *A6 done (2026-09-23):* deleted `glue/loading.py` (via `rm`),
   `loading_strategy` from `BaseGlue`, every family, `Component` (and its
   generated signature), and the shortcuts, `Glue.LoadingStrategy`, the
   `GlueObjectEntry.loading_strategy` field, `BaseGlue.load_state`, and
   `SequenceGlue`'s `load_state`/`SequenceLazyLoadNotSupportedError`/
   `_reconstructed`. `BaseGlue.entry` always carries `get_computed_data(include_all=True)`.
   Rows: `BaseGlue._refreshed_output()` is the refresh's re-derived output;
   `QuerySetGlue` extends it with `_loaded_window()`, so introduction carries no
   rows while a refresh does. Client: removed `_ensureLoaded`/`retryLoad`/
   `_loadPromise`/`_loadError`/`loading` from `FieldBackedGlueProxy`, the field
   and materializer hooks, `record.loadingStrategy`, and `base.js`'s
   strategy-seeded `_loaded` (the queryset proxy owns its own `_loaded = false`).
   Tests migrated: callables that only used `load_state` as a neutral call now
   use a refresh or a fixture `ping`; `IntroductionTestCase` replaces the lazy
   cases. Gates: 596 Python, 111 JS, 35 E2E / 10 xfailed. `AGENTS.md` still
   lists `loading.py`/`LoadingStrategy`/`TemplateGlue` — updated in the docs pass.
7. Queryset bookkeeping (`_last_query_params`, `_loaded_row_count`) is signed in
   `get_identity()` (`queryset.py:136`); the audit rules "MOVE out of identity"
   and state-model.md §2 names `loaded_row_count` a non-parameterized
   reconstructor, i.e. `state_snapshot`. Prerequisite for B7's queryset refresh.
   *A7 done (2026-09-22):* `QuerySetGlue._retained_state()` adds
   `last_query_params`/`loaded_row_count`; `get_identity()` no longer carries
   them; reconstruction reads them from `state_snapshot`. Test
   `test_cursor_memory_is_signed_as_retained_state_not_identity`. Gates: 592
   Python, 34 E2E / 10 xfailed.

E. 1.0.2 features missing from this branch (found 2026-09-22). `v1.0.2/base`
   has 23 commits that are not ancestors of `v1.1/state-model`. Eleven are the
   component workstream (A5 ports them by behavior). Of the other eleven:
   - **Missing, must port:** `label_formatter` on `Glue.choices` with request
     plumbing, per-choice label flag, and client `choiceLabelHtml` (`868ebf7`,
     `c346634`, `0116b4e`, `8c7f216`) — it needs each choice's `obj`, which
     therefore stays on every choice, implicit sources included (`obj` = `pk` +
     `__str__` there); searchable choice sources return their first
     `search_limit` rows when unfiltered and `search_fields` defaults to `fields`
     (`1ea1ad1`; the branch still returns `[]` and a test asserts it); model pk
     always exposed unless excluded (`495c427`); reject `'__all__'` as an element
     of `fields`/`exclude` (`b8a4026`).
   - **Verify behaviorally:** `9aebaf8` (callable return annotation breaking the
     call — fix targets code this branch rewrote); `6029209` (public `load()`
     seam — confirm no consumer calls `.load()`; superseded by `$refresh()`).
   - **Equivalent / superseded:** `f5d8b96` (shortcuts already accept
     `request=None`), `bf7df07` (redirect moved to `effects.redirect` in A4).
   A5's `state-model.md` implicit-source text ("label and value only") must say
   `obj` carries `pk` and `__str__` for the label formatter.
   *Progress (2026-09-22):* ported `label_formatter` (stored as a dotted path so
   only a string crosses the allowlisting unpickler; lambdas/closures rejected),
   request plumbing, `has_html_label`, client `choiceLabelHtml`/`choiceLabelText`,
   `1ea1ad1` (the fight page's two searchable-choice E2Es now expect the
   unfiltered first page after a cleared search — 1.0.2 kept the stale `count(0)`
   assertion), pk always exposed, `'__all__'`-as-element rejection. New tests:
   `test_choice_labels.py` (15), `choice_label.test.js` (4), pk/`__all__` cases
   in `AllFieldsTestCase`. **Security fix found while porting `495c427`:** a
   primary key listed in `fields` was in the derived editable projection
   (`BigAutoField.editable` is `True`), so a client could submit `{'id': <other
   pk>}` and retarget the row a save writes; the pk is now never editable
   (derived set skips it; explicit `editable=['id']` is a declaration error).
   Regression test `test_exposed_primary_key_is_never_client_editable`.
   Gates: 582 Python, 106 JS, 34 E2E / 10 xfailed.
   *Behavioral checks:* `9aebaf8` reproduced here in a different form — a Glue
   return annotation imported only under `TYPE_CHECKING` was silently classified
   as non-Glue (`returns_glue: False`) and the call then failed. Fixed in
   `_resolve_glue_result_annotation`: an unresolved return annotation is
   evaluated against every loaded `BaseGlue` subclass by name (ambiguous names
   skipped); unresolvable non-Glue annotations stay ordinary results. Tests:
   `test_callable_return_annotations.py` (3). `6029209`'s public `load()` does
   not exist on this branch and is superseded by complete introduction plus
   `$refresh()` (see B7 for the two call sites).

**Order (user-approved 2026-09-22):** A4, A5, A7, B7, A6, then B6, B13, B8,
B9–B12. `docs/` rewrite last.

B. Spec contracts not implemented:
6. ADR 003 `Glue.view` dispatch: same-origin request to the real URL with a Glue
   `Accept` media type, a response middleware producing the `{html, objects}`
   envelope, `Vary: Accept`, HTML-only negotiation, the system check that the
   middleware is present and last; delete `/__dg__/glue_view/`, the request
   wrapper, and the redirect loop. (Security: closes the middleware bypass.)
7. `$refresh()` (§6/§7) with `{submit: true}`; call-less refresh entries
   authorized as `refresh`. A queryset refresh re-runs its signed last query
   over the loaded window (state-model.md §10), which needs A7 first. Replaces
   every `load_state()` consumer call before A6 deletes it. Also: the fight list
   `saveFight` should `await fight.$refresh()` after the row form saves (it
   called a nonexistent `fight.load()` in the committed tree; the call was
   removed pending B7), and the portal's
   `time_entry_form_field_content.html` `await {{ glue_form }}.load()` (1.0.2's
   public `load()` seam, `6029209`) is deleted in the consumer migration since
   every object now introduces complete.
   *B7 conformance record (pre-edit, 2026-09-22).* (1) Phase 6 gap closure.
   (2) state-model.md §6 "`$refresh()` itself remains an ordinary addressed
   request" through "Neither form is a reset"; §3 authorization point 2
   ("with `kind='refresh'`, `'update'` or `'call'` as the interaction
   requires"); §10 "A queryset's rows ... `$refresh()` on a queryset re-runs its
   signed last query over the window already loaded". (3) Removed: the A3 rule
   that an entry with neither `call` nor `reintroduce` is malformed — that exact
   shape is the spec's refresh. (4) Mapping: a call-less entry is a refresh;
   reconstruction authorizes `call` / `update` (call-less with `updates`) /
   `refresh`; the call-less path hydrates the token's canonical draft plus any
   admitted `updates` (shared with the call path), re-derives all downward
   output, and returns the entry with `result: None`; the queryset re-derives
   rows from its signed last query over its loaded window (first batch before
   any query) without advancing its cursor; client `$refresh({submit})` on
   every proxy sends that entry through the per-address queue and resolves to
   the proxy.
   *B7 progress (2026-09-22):* server side done — `_hydrate` (shared by call and
   call-less paths), `_refresh_entry`, reconstruction kinds, queryset
   `_loaded_window()`; `test_refresh.py` (6). **Blocking finding — model lost
   update:** `ModelGlue._load_client_state` treats every signed editable value
   that differs from the *current* row as a draft, so a stale baseline (row
   changed out of band) is indistinguishable from a user edit. A refresh keeps
   the stale value instead of refetching it (spec: "a model keeps its editable
   overlay while refetching persisted data"), and an ordinary save writes the
   stale value back over the other writer's change. `test_refresh_re_reads_
   persisted_data_without_a_result` fails on purpose until this is fixed.
   *User decision (2026-09-22): option (a) — sign the drafted paths.*
   Conformance: state-model.md §4 family table (`ModelGlue` signs "exposed
   editable values (row baseline plus acknowledged draft overlay)") and §6 ("a
   model keeps its editable overlay while refetching persisted data"). Mapping:
   `ModelGlue._retained_state()` adds `'$draft': [paths]` when the overlay is
   non-empty; `BaseGlue._retained_draft(policy)` is the token's acknowledged
   draft (every signed editable value) and `ModelGlue` narrows it to the `$draft`
   paths; `_hydrate` uses it, so every other editable field comes from the
   freshly fetched row. A drafted field still wins over a changed row
   (conflict detection is the separate opt-in version contract).
   *Done:* `$draft` signed when non-empty; `_retained_draft` hook; a successful
   save clears the overlay (`_rebase_draft` removed — the saved row is the
   baseline, so the successor snapshot is unchanged in value and drops
   `$draft`). Tests: out-of-band row change supersedes an undrafted baseline;
   saving one field keeps a concurrent change to another (the lost-update
   regression); save changing nothing omits the token; saving a signed draft
   re-signs it as baseline. Client properties come from schema only, so
   `$draft` never surfaces on a proxy. Gates: 601 Python, 34 E2E / 10 xfailed.
   *Client done:* `$refresh({submit = false} = {})` on `BaseGlueProxy` runs the
   ordinary queued pipeline (`_callAttribute(null, {}, {submit})`); an
   unsubmitted refresh sends no `updates` and blanks the capture's updates so
   reconciliation keeps pending edits. `refresh.test.js` (3); E2E
   `test_model_refresh_re_reads_a_row_changed_out_of_band`; the fight list
   `saveFight` now awaits `fight.$refresh()`. Gates: 601 Python, 109 JS, 35 E2E
   / 10 xfailed.
   **Queryset views — user decision (2026-09-23): option 1, the last query
   wins.** Client `filter()`/`orderBy()`/`slice()` views share one address and
   one signed cursor. A queryset refresh re-runs the signed last query; the
   client routes the rows only to the view whose filter/order match the signed
   `last_query_params` (sliced views never match). `$refresh()` on any other
   view marks it unloaded and re-queries it (pages beyond the first batch are
   not restored — same as switching views today). Rows route only when the
   latest entry carried them: `addressRecord.receivedComputedData` is the
   `computed_data` the latest entry carried (null when omitted). **Fixed
   alongside:** `_afterRecordRefresh` used the merged `computedData`, so after
   any later queryset call it re-synced the base view from stale page-load rows
   (two `loadMore()`s lost the middle batch). Tests: `queryset_refresh.test.js`
   (3). **B7 done.** Gates: 601 Python, 112 JS, 35 E2E / 10 xfailed.
   Consumer note: spire's scroll widget calls the queryset's legacy `refresh()`
   (reset every view and re-query the first page), which stays; it is not
   `$refresh()` (keep the window) and must not be silently swapped.
   *B6 conformance record (pre-edit, 2026-09-23).* (1) Phase 6 gap closure,
   security. (2) ADR 003; state-model.md §6 "`Glue.view` is an HTML transport"
   through "existing `Glue.view(url)` ergonomics remain intact". (3) Removed:
   `/__dg__/glue_view/`, `resolver/view_fragment/` (`GlueViewFragmentResolver`,
   `ViewFragmentRequestContext`, `ViewFragmentHttpRequest`), the manual redirect
   loop, `DJANGO_GLUE_VIEW_MAX_REDIRECTS`, the view-only error codes,
   `GlueContextManager`'s `glue_context_request` indirection, and the client's
   `glueViewUrlPath`. (4) Mapping: `GlueViewMiddleware` (`django_glue/middleware.py`)
   negotiates `Accept: application/vnd.django-glue.view+json` on 2xx,
   non-streaming HTML responses into `{is_glue_template_response: true, html,
   objects}`, sets `Vary: Accept` on every HTML response, passes everything
   else through; a Django system check (`django_glue.E002`) fails startup when
   it is absent or not last in `MIDDLEWARE`; client `GlueView` requests the
   real URL (GET payload → query string, POST → CSRF-protected JSON), follows
   redirects natively, and treats a response without the marker as a
   non-fragment outcome; `sendRequest` parses JSON only for JSON responses.
   *B6 done (2026-09-23):* as mapped; `resolver/view_fragment/` and its three
   test modules deleted (via `rm`); renderers return `null` without touching the
   DOM when a view response is not a fragment. The test project lists the
   middleware last. Tests: `test_view_middleware.py` (envelope + `Vary`,
   pass-through for non-HTML/redirect/non-2xx/streaming without materializing,
   real-route dispatch, **a path-scoped middleware blocks a negotiated view
   request** — the ADR's security property — and the `django_glue.E002` check);
   `test_html_response.py` and the JS view tests rewritten for the real URL.
   Gates: 573 Python, 113 JS, 35 E2E / 10 xfailed. **Consumer migration:**
   every project must add `django_glue.middleware.GlueViewMiddleware` as the
   last `MIDDLEWARE` entry (startup fails otherwise).
8. `authorize()` at all three points: reconstruction uses `refresh`/`update`/
   `call` as the interaction requires (today always `call`), and each admitted
   draft is authorized as `update` with its attribute path before applying.
   *B8 conformance record (pre-edit, 2026-09-23).* (1) Phase 6 gap closure.
   (2) state-model.md §3 authorization point 3 ("before each authorized callable
   runs and before each admitted draft is applied, with `attribute` naming the
   exact path") and roadmap "Implement `authorize()` as a pure predicate called
   at introduction, reconstruction, and attribute invocation". Point 2
   (reconstruction kinds) was done in B7. (3) Nothing removed. (4) Mapping:
   `_hydrate` — shared by the call and refresh paths — authorizes each admitted
   update as `GlueOperation(kind=UPDATE, attribute=path, required_access=<the
   path's declared access>)` after admission and before any draft is applied; a
   denial is `GlueAuthorizationError` (`not_authorized`, per-address).
   *B8 done (2026-09-23):* as mapped. Tests: `DraftAuthorizationTestCase` (each
   admitted draft authorized with its path; a denied draft fails before any
   draft applies). Gates: 582 Python, 35 E2E / 10 xfailed.
9. Transient callable-result capability capping at issuance.
   *B9 conformance record (pre-edit, 2026-09-23).* (1) Phase 6 gap closure,
   security. (2) state-model.md §10 "The introduced capability cannot exceed
   the caller's effective capability" and the transient-result table ("Enforced
   at issuance, baked into the child's signed policy, and re-intersected with
   current authorization on every request"). (3) Removed: a returned object
   keeping its own configured access regardless of the caller. (4) Mapping:
   `BaseGlue.cap_access(ceiling)` lowers `access` to the ceiling when it is
   higher; `ModelFieldResolutionMixin` extends it to re-derive `editable` from
   the stored declaration (its derived default is access-gated);
   `process_attribute_call` caps a newly issued result to the caller's access
   before `introduce()`, so the child's first signed policy carries the capped
   access. Current authorization is already re-checked on every request.
   *B9 done (2026-09-23):* as mapped (`ModelGlue`/`QuerySetGlue` store
   `_editable_declaration`). Tests: a `VIEW` caller's `DELETE` result is issued
   at `VIEW` with no editable paths; a lower-access result is never raised to
   the caller's. Gates: 580 Python, 35 E2E / 10 xfailed.
10. Keyed-collection item reintroduction, and the row-2 factory skip for live
    collection items.
    *Finding (2026-09-23):* collections ignore `live_children`, so the successor
    `children` map is only what this request produced. After a non-query
    queryset call (`count()`) it is empty; after `loadMore()` it holds only the
    new batch; a reconstructed sequence has no items at all. The client then
    disposes every dropped row — rows stay rendered as tombstones but reject
    calls (`save()` on a first-batch row fails after `loadMore()`).
    *B10 conformance record (pre-edit).* (1) Phase 6 gap closure. (2)
    state-model.md §10 slot table (row 2: live, non-participating → factory does
    not run, address copied forward; row 4: live and listed in `reintroduce` →
    factory runs, same address), "Reintroducing an expired child", §8 keyed
    membership; ADR 011 (collection owns item keys). (3) Removed: the A3 scope
    note that collection keys are not reintroducible; collection items bound
    without `introduce()` (so a sequence of components was never mounted).
    (4) Mapping: `BaseCollectionGlue._bind_children` binds the keys returned by
    `_membership(live_children, produced)` — produced items introduce through
    `introduce()`, a live key listed in `reintroduce` is rebuilt by
    `_rebuild_item(key)`, any other live member carries forward by address with
    no factory. Membership per family: formset — its produced forms
    (authoritative signed membership); sequence — its signed `item_keys` (items
    cannot be rebuilt, so `_rebuild_item` is None and reintroducing an item fails
    admission); queryset — its loaded window: a new or restarted query replaces
    it, a continuation (`seek_key`) appends to it, a refresh re-derives it, any
    other call carries it (and its relation children) forward. `_admit_reintroduce`
    takes the incoming policy; a collection also admits live item keys when its
    family can rebuild items. A queryset rebuilds a row by re-fetching its pk
    from the signed base queryset (a row gone from the queryset is dropped).
    *B10 done (2026-09-23):* as mapped. The queryset tracks the window change
    (`WindowChange.REPLACED`/`EXTENDED`) for the request: a query with no
    `seek_key` replaces membership, and a continuation extends it.
    `loaded_row_count` resets only when the query parameters change, so a
    restart over the same parameters can still slice as wide as the rows
    already loaded. Rows that answer a query this request ride as introduced
    entries even when the address map is unchanged (`_introduced_entries`
    override), so a refresh re-syncs row data. Tests:
    `test_collection_membership.py` covers:
    - a non-query call keeps the rows;
    - a continuation keeps earlier rows at the same addresses;
    - a restart replaces the window;
    - reintroducing a live row re-fetches it at its address;
    - reintroducing a deleted row drops it;
    - a sequence refresh carries its items forward;
    - reintroducing a sequence item fails admission;
    - an item refused `INTRODUCE` is left out.

    Gates: 590 Python, 113 JS, 35 E2E / 10 xfailed.
11. Relation-owned drafts: atomic save + attach through the signed reverse-FK /
    M2M relation, relation membership/count reconciliation in the same response,
    reject an unsaved owner.
    *Finding (2026-09-23):* a relation queryset already gets `ADD`, and gets
    `VIEW` when its model owner is unsaved. Its `new()` builds a bare
    `model(**initial)`, though, and `save()` never attaches: a reverse-FK draft
    fails validation on the missing owner, and an M2M draft saves unattached.
    *B11 conformance record, attach part (pre-edit).* (1) Phase 6 gap closure.
    (2) state-model.md §4 "Relation membership" (`relation.new(initial)`
    introduces one unsaved member; on first save a reverse FK injects the owner
    identity server-side; an M2M relation saves and adds in one transaction; an
    unsaved owner cannot expose `new`; a custom through model needs an explicit
    callable) and §4 "Creation is an ADD operation" ("that transaction also
    attaches the object to the exact signed relation"). (3) Removed: the
    `hasattr(self, 'instance')` unsaved-owner check in
    `_construct_relation_child`. (4) Mapping:
    - New `OwningRelation` (`objects/django/relation.py`) holds the owner model
      path, the owner pk and the relation accessor name. It is built only for a
      saved owner and a reverse FK or auto-through M2M, so it is None exactly
      when generic creation is unavailable.
    - `_construct_relation_child` takes the owner and relation name. A to-many
      child gets `ADD` only when the introducer has `ADD` and the relation
      exists.
    - `QuerySetGlue` signs `relation` in its identity, and `_row_glue` passes it
      to a draft.
    - `ModelGlue` signs `relation` while `target_pk` is null. `save()` runs in
      `transaction.atomic()`: it fetches the owner, sets the reverse FK before
      `full_clean`, and does the M2M `add` after saving.

    Membership reconciliation in the same exchange is a separate decision,
    brought to the user.
    *B11 attach part done (2026-09-23):* as mapped. The work surfaced three bugs
    that predate B11, all fixed:
    - A reverse-FK relation queryset could not be reconstructed. Its related
      manager filters on the owner instance, which the unpickler allowlist
      refuses (a datetime field). The new `_related_queryset` filters on the
      owner pk.
    - `new(initial)` values were lost on the next request: they sat on the
      instance, not in `$draft`. An unsaved instance now retains its whole
      signed editable state as draft.
    - `new(initial)` could not take a foreign-key pk. `new()` now applies
      `initial` through the draft's `_load_client_state`, the same decode path
      as client updates.

    Tests in `RelationDraftAttachTestCase`:
    - an M2M draft is added to the owner relation, and its `relation` leaves the
      identity after saving;
    - a reverse-FK draft gets the signed owner, overriding a client-supplied FK;
    - an invalid draft attaches nothing;
    - a deleted owner fails the save and rolls back.

    No custom-through fixture exists, so `creatable` returning None for a
    custom-through M2M is untested. Gates: 594 Python, 35 E2E / 10 xfailed.
    *B11 reconciliation (user decision, 2026-09-23): co-batched producer
    refresh.*
    - A relation draft's first `save` carries a call-less entry for its
      producing relation in the same batch. The draft's record `owner` has
      `path: null` and its signed identity has `relation`.
    - The resolver runs entries in order, so the refresh sees the committed
      attach and re-runs the relation's last query. Ordinary query semantics
      win, as the spec says.
    - Each entry is authorized by its own token, and the server gained nothing.
    - Client: `sendAttributeRequest({companions})` appends call-less entries.
      `_singleCall` captures each companion without updates, and reconciles
      its entry after introductions (an error entry or a disposed record is
      ignored). `GlueModelProxy._singleCall` adds the producer.
      `_callAttribute` now passes its options through.
    - Known consequence, accepted: the saved row also appears at its pk address
      in the relation, beside the draft's transient proxy, until the next
      refresh. This matches root `new()` behavior today. A general rule that a
      collection adopts a live draft's address for its pk could come later
      without changing the wire format.

    Tests:
    - `test_relation_refreshed_in_the_same_batch_sees_the_new_member`
      (resolver-level);
    - `client_js/tests/relation_draft.test.js` (a companion is sent and the
      relation's items reconcile; a root draft saves alone).

    *B11 done.* Gates: 595 Python, 115 JS, 35 E2E / 10 xfailed.
12. Abort a single-address in-flight request on disposal where possible.
    *B12 conformance record (pre-edit, 2026-09-23).* (1) Phase 6 gap closure.
    (2) component-system.md "Disposal" ("Disposal cancels queued calls,
    aborts a single-address in-flight request where possible … A shared
    batched request is not aborted; response entries for disposed generations
    are discarded individually"). Queued-call cancellation and per-generation
    discard already exist. (3) Nothing removed. (4) Mapping:
    - `sendRequest` accepts a caller `signal` and chains it into its timeout
      controller.
    - `sendAttributeRequest` forwards `signal`.
    - `_singleCall` gives a request that carries only its own address (no
      companions) an `AbortController`, held on the record as
      `inFlightController` while the request is in flight.
    - `GlueAddressRecord.dispose()` aborts it.
    - An abort caused by disposal resolves as a discarded call (`undefined`),
      the same outcome as a late response for a disposed generation, rather than
      an error.
    - A request that carries companions is shared, so it is never aborted.

    *B12 done (2026-09-23):* as mapped. Tests in
    `client_js/tests/disposal_abort.test.js`:
    - disposing during a single-address call aborts it, and the call resolves
      `undefined`;
    - a call with companions gets no signal;
    - the transport chains a caller signal into its own controller.

    Gates: 595 Python, 118 JS, 35 E2E / 10 xfailed.
13. Token and encoded-query size limits before queryset unpickling (roadmap: "not
    deferred").
    *B13 done (2026-09-23):* state-model.md §10 bounds 1–3 (bounds 4–5, batch
    and page aggregates, are group C). `GluePolicy.from_token` refuses a token
    over `DJANGO_GLUE_MAX_POLICY_TOKEN_BYTES` (128 KiB) before signature
    verification; the token serializer refuses a decoded envelope over
    `DJANGO_GLUE_MAX_POLICY_DECODED_BYTES` (128 KiB) before parsing (both
    `GlueInvalidPolicyError`); `unpickle_query` refuses a continuation over
    `DJANGO_GLUE_MAX_QUERY_ENCODED_BYTES` (64 KiB) before base64 decoding and
    checks the decoded query's model against the signed `model_class_path` (the
    spec's "must immediately match that signed identifier") — `choices=`
    sources now sign their model path too. New `pickle_query` enforces the
    continuation bound at issuance (loud render-time failure instead of an
    unreadable token) and replaces `QuerySetGlue._encode_queryset_query`.
    Defaults are provisional pending the roadmap's production measurement.
    Tests: 3 continuation-bound tests, 2 token-bound tests. Gates: 578 Python,
    35 E2E / 10 xfailed.

C. Roadmap "Security hardening" (roadmap says these do not gate the redesign —
   user to rule on scope): payload/nesting/count limits, invalid-token throttling,
   anonymous-session avoidance, session-rotation recovery, CSP-compatible init,
   DOM-event-name startup check (the collision check exists at class creation).

D. Open questions, not spec gaps: the component workstream's gate names a
   time-entry dashboard ported into `test_project` (absent on both branches);
   tombstone GC; ADR status headers need updating after implementation.

*Dashboard gate decision (2026-09-23):* The user dropped the `test_project`
port requirement. The dashboard belongs in `stratusadv-portal`, where
`TimeEntryDashboard` is already stamped on the dashboard page. Portal has an
E2E for its add-entry modal and project choices
(`app/time_tracker/tests/test_e2e/test_time_entry_form.py`) and a dashboard
URL smoke test, but no dashboard week-navigation E2E was found. The component
consumer gate should cite portal E2E coverage after the portal migrates to
the state-model branch; the portal's current branch uses the older component
runtime.

*Portal dashboard E2E conformance record (pre-edit).* (1) Phase 6 consumer
gate, in the actual portal rather than a duplicate `test_project` fixture.
(2) component-system.md §4 (server-resolved component parameters and retained
address across parameter transitions), §5 (Django template-tag stamping and
keyed day children), and §6 (morphing after structural week changes).
(3) The removed gate asked for an artificial dashboard port; the existing
portal E2E only opens an add-entry modal. (4) No runtime field, class, or
public method is added. A portal browser test will assert the requested week
renders seven day components and that Previous/Next advance the rendered
dates and URL without a full-page navigation. This pins the real consumer's
component behavior and remains useful after its Glue dependency migrates.

*Done:* Added
`stratusadv-portal/app/time_tracker/tests/test_e2e/test_time_entry_dashboard.py`
on the portal component branch. It verifies seven keyed day cards, Previous
and Next updating dates and URL, and no full-page navigation. The new E2E
passed alone (1 passed, 38.70s); the complete portal time-tracker E2E folder
passed (2 passed, 55.33s), including the existing add-entry modal test.
Portal Ruff on the new file and `git diff --check` passed. The portal branch
still depends on the older Glue component runtime; rerun these E2Es after
its dependency migrates to the state-model branch before treating portal
consumer compatibility as verified. The roadmap phase-6 gate now names this
real portal suite and no longer asks for a `test_project` dashboard copy.

**Component audit leftovers (2026-09-23).** Item 2 below (legacy manifest
API) is verified clean by search. Of item 1's list, `__signature__`, the
event-name list, `value_adapters`, and mount/authorization order
(`introduce()`) were done earlier.

The tag already enforces the Keys rules:
- a loop needs a key;
- a direct `forloop.counter` or `forloop.counter0` key is rejected;
- duplicate target/key pairs under one parent fail, including outside a loop;
- keys are canonicalized with their types.

The registry enforces tag-name collisions (`E001`) and discovery.

*Root scanner finding.* The scanner had no tests. The probe found three
defects:
1. Omitted optional end tags (`<li>a<li>b`, `<p>`, `<td>`/`<tr>`) broke the
   depth count, so valid single-root HTML was rejected.
2. A stray end tag (`</p>`) was misreported as text outside the root.
3. An entity outside the root passed as if it were not text.

The injection offset was also computed with `str.splitlines()`, while
`HTMLParser.getpos()` counts `\n` only, so a form feed or ` ` before the
root shifted the injection point.

*Conformance record (pre-edit).* (1) A5 component audit. (2)
component-system.md §5 ("registered components with a single root element")
and §6 ("A component template has a single root element"). (3) Removed: the
depth counter. (4) Mapping:
- The scanner keeps a stack of open elements. An end tag closes up to its
  matching open element and is ignored when nothing matches.
- The root must end closed, since a still-open root at the end means sibling
  content may belong to it or follow it ambiguously.
- An entity or character reference at depth 0 is text outside the root.
- The offset is computed from `\n`-split lines.

*Done:* as mapped. `test_component_root.py` has 19 cases.

*Bootstrap finding.* `{% django_glue_init %}` renders in `<head>`
(`test_project/templates/base.html:220`), before any body stamp. A stamped
component reaches the client only through its root's `data-glue-entry`, which
carries the component's own entry. Its children (a child-slot form, a queryset
property) are serialized nowhere at page load, which contradicts the page-load
contract (state-model.md §10: every introduced entry and its children arrive
as flat addressed entries). HTML responses are unaffected: they serialize the
context manager after rendering.

*Conformance record (pre-edit).* (1) A5 component audit. (2) state-model.md
§10 "Page load" and "there is likewise no lazy loading"; component-system.md
§4 "Mount" (the first token and initial HTML carry the introduced object).
(3) Removed: the single-entry `data-glue-entry` attribute. (4) Mapping:
- The stamp's root carries `data-glue-objects`: a JSON array of the
  component's entry followed by `_serialized_child_entries()`, the same flat
  shape as an `objects` envelope.
- `registerComponentsFromDom` loads the entries whose address has no record
  yet through `loadObjects`. Existing records keep being advanced by response
  `objects`.

*Done:* as mapped. `Component.render()` injects the same subtree list. Tests:
- `test_stamped_component_root_carries_its_children_entries` (red before the
  fix);
- JS: "a stamped root introduces its children entries".

The 10 xfailed E2Es were reviewed: they are the strict-xfail morph-spike
evidence in `test_lab_morph.py` (the `replace`/`idiomorph` state losses), by
design. Nothing to fix. Gates: 615 Python, 119 JS, 35 E2E / 10 xfailed.

*Events and disposal checked against component-system.md §7, no change
needed:*
- declared-only emission;
- the DOM-name collision check at class creation;
- `$address` rejected at emit;
- a Glue object in the detail is rejected by the encoder (now pinned by
  `test_event_detail_rejects_a_glue_object`);
- events dispatch after reconcile and after the component morph, from `$el`,
  which follows the address and is null after disposal;
- `Glue.from()` fails after disposal;
- `$on` listeners are cleared on disposal.

**The component audit (item 1) is complete.**

*Tombstone finding (D item, 2026-09-23).* Disposed records stay in the
registry forever. Reintroducing a disposed address calls
`GlueAddressRecord.introduce`, which resets `disposed`, so every held
reference to the old proxy revives and targets the new incarnation. The test
`disposal.test.js` "a response for a disposed-and-reintroduced address is
discarded" asserts that revival.

*Conformance record (pre-edit).* (1) A5 / D tombstone GC. (2)
component-system.md "Disposal follows address ownership": "Existing references
to the disposed proxy become tombstones and reject later calls rather than
silently targeting a future object. Reintroducing the same canonical address
creates a new proxy generation and calls `mount()` again." (3) Removed: the
disposed-revival branch in `GlueAddressRecord.introduce`, and the revival
assertion. (4) Mapping:
- `GlueAddressRegistry.dispose` deletes each doomed record from `records`
  after disposing it. The old proxy keeps its own disposed record as its
  tombstone, which also releases it for GC.
- A later introduction of the address builds a fresh record and proxy.
- In-flight responses for the old record are already discarded by the
  `getRecord(address) !== this._record` check in `_singleCall`.

*Done:* `GlueAddressRegistry.dispose` removes disposed records, and a later
introduction creates a new proxy while held references remain tombstones.
The updated `test_detail_model_delete_disposes_proxy` passes. JS gate: 119
passed. `just test-e2e -q`: 35 passed, 10 xfailed, 2 teardown errors.
The errors are JavaScript null dereferences (`items` and `loading`) in the
gorilla list demo during `test_queryset_filter_order_slice_demo` and
`test_create_model_modal_demo`; neither is in the tombstone test. The same
filter demo error reproduces alone (1 passed, 1 teardown error). Track and
resolve these before recording the final E2E gate green.

*Gorilla list teardown errors — conformance record (pre-edit).* (1) A5
component/consumer migration gate: the E2E demo must remain error-free while
queryset results replace rows. (2) state-model.md §4 and §10 make projected
relations independently addressed children, and component-system.md §7 says
removed collection children are disposed and old references become tombstones.
(3) The legacy list template assumes every row's `skills` child remains live
through Alpine's render of a departing card. (4) No new field, class, or public
method is needed. The two list expressions that read `gorilla.skills.items`
and `gorilla.skills.loading` will tolerate the brief null child lookup during
row replacement. The focused filter E2E is the red-capable check.

*Done:* the gorilla list's projected-skills expressions tolerate a disposed
child while Alpine removes an old row. The two focused E2Es pass (2 passed).
The full `just test-e2e -q` gate is green: 35 passed, 10 xfailed, 2 existing
pytest collection warnings; no JavaScript teardown errors.

Required remaining A5 work:

1. Audit and finish the component contract. The generated constructor still
   has a generic `**parameters` Python signature; there is no dedicated
   `__signature__`. Review root-entry/bootstrap semantics, duplicate names,
   mount/authorization order, root scanner edge cases, event names/details,
   and source-scoped event delivery through morph/disposal. The E2E fixture
   currently sets `value_adapters=[]` for a plain list because the legacy
   sequence adapter otherwise converts it; the spec says ordinary serializable
   lists should remain plain data.
2. Remove remaining legacy manifest API and tests, especially
   `GlueManifest`/`BaseGlue.manifest`, `serialized_manifests`,
   `GlueResponse._serialize_result`, `client.loadManifests`/
   `resolveManifest`/`_collectManifests`, and old result-shape branches in
   `client_js/src/proxies/base.js`. Search `manifest_list`,
   `is_glue_manifest`, and `is_glue_template_response`, excluding built assets
   and historical docs. This is not a compatibility release.
3. Complete the docs rewrite beyond the new component/event guides; old
   architecture, codewalk, changelog, and some family pages remain stale.
   Remove stale element-compiler text fully from `component-system.md`, and
   resolve remaining active design text about lazy/defer mount and stamp-level
   handlers in favor of the user's templatetag direction.
4. Run the complete Python, JS, build, Django check, docs, and E2E gates.
   Build JS before E2E. The `just python` recipe quotes all arguments into
   one path and fails for `manage.py check`; use `.venv/bin/python` directly.
   The docs strict build may need approved network access for the Python
   inventory. Review Ruff and `git diff --check`. Do not commit until asked.

*ADR and docs pass (2026-09-23):* ADR 002–009, 011, and 013 headers and the
decision index now reflect their branch implementation. The repo-root
`AGENTS.md` no longer lists the removed manifest, template, loading, or view
resolver surfaces. The active `docs/` pages were rewritten for the addressed
protocol, current installation, projections, access levels, families,
components, and `Glue.view`; removed template-proxy and superseded future
roadmap pages were deleted with the editor tool. Historical v1.0 changelog
entries remain labeled as history. The stale HTML-envelope transition and
element-compiler text was removed from `component-system.md`. Final gates
were run after the pass: `just test` 616 passed / 45 deselected;
`just js-build` passed (26.8 KB); `just js-tests` 119 passed;
`just test-e2e -q` 35 passed / 10 xfailed / 2 existing pytest collection
warnings; `.venv/bin/python manage.py check` found no issues; `just docs`
strict built successfully (network access was needed for the Python inventory);
`git diff --check` clean. Ruff on all 68 touched Python files reports the
repository's broad pre-existing style noise. A focused `--select F` check
found only two F401 imports already present at `HEAD` in `glue/function.py`
and `test_queryset_pagination.py`; no new F findings.
The design README and roadmap status lines now distinguish branch
implementation from release review; the roadmap's former open-constraints
list is labeled a verification checklist. The dashboard gate is resolved in
favor of portal E2E coverage, recorded above; the portal tests must be rerun
against the state-model dependency during consumer migration.

*Consumer migration finding (2026-09-23):* The earlier component prototype's
`design/REINTEGRATION.md` identified two Parhelion fixture views that call the
removed `Glue.template()` API. Both calls still exist in
`parhelion/fixtures/pilot/catalog/views.py` and
`parhelion/fixtures/seeded/views.py`. Include them when migrating consumers;
the latter is a seeded diagnostic for an unresolvable target. The prototype's
reintegration and agent-rule documents were removed during the merge into
`v1.1/base` because they describe the state model as shelved and the old wire as
active.

`client_js/dbg_tmp.mjs` is an existing untracked user debug script: leave it
alone. All file edits must use the editor/patch tool, not shell scripts or
redirection. Do not add code comments unless asked. Do not stage, commit,
push, reset, or rebase without the user's request.
