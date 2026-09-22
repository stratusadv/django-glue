# Reactive State-Model Server Refactor Handoff

## Objective

Finish the reactive-system redesign described by the roadmap. Phases 1–5 and phase 6 slices A1–A4 are complete. A1–A4 were reviewed, corrected, and committed on 2026-09-22. A5, the component port and consumer migration, remains unstarted and needs separate authorization.

The current branch is intentionally making a clean break from the legacy runtime. Do not add a compatibility envelope for old metadata, state, or `manifest_list` shapes.

## Design authority

Treat the design documents as the specification. Read them in this order before making further architectural decisions:

1. `design/reactive-system/design.md`
2. `design/reactive-system/state-model.md`
3. `design/reactive-system/component-system.md`
4. `design/reactive-system/roadmap.md`

For the current work, `state-model.md` is primary and roadmap phase 5 defines the gate. Particularly relevant parts of `state-model.md` are:

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

- Worktree: `/home/chasemossing/stratus-dev/django-glue-state-model`, branch `v1.1/state-model`.
- Baseline: `44803c0` ("Shelve reactive-system state-model work in progress"). The tree was clean at baseline; the shelve commit already contained the handoff-time work (both then-red focused tests were fixed in it).
- The venv was created fresh in this worktree (`uv venv .venv --python 3.11.14 && uv sync`). Its editable install is bound to **this** worktree's source. Do not symlink the main worktree's `.venv` — its editable finder is hardwired to the main worktree path.
- The working tree holds the entire phase 3–5 increment (attribute-hierarchy removal, ModelGlue hydration cutover, (4a)/(4b)/(4c), and the phase-5 client + server integration) uncommitted on top of baseline `44803c0`. New files at the time of writing: `django_glue/serialization.py`, `django_glue/tests/glue/test_update_admission.py`, `client_js/src/runtime/`, `client_js/tests/state_model.test.js`, `client_js/tests/family_api.test.js`. Inspect every overlapping diff before editing; the committed history contains the wider reactive-system branch.

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

## Handoff warning

The committed history contains the wider reactive-system branch, including client and documentation edits outside this server task. `docs/` still references the removed attribute hierarchy (`architecture.md`, `codewalk.md`, `changelog.md`, `docs/future/attribute-glue-unification.md`) and was deliberately left untouched — it is rewritten with the phase 6 consumer migration. Treat the existing tree as user-owned; inspect every overlapping diff before editing.

## Agent handoff prompt (ready to paste)

```text
You are continuing the django-glue reactive-system state-model refactor in the
worktree /home/chasemossing/stratus-dev/django-glue-state-model (branch
v1.1/state-model). Read STATE_MODEL_HANDOFF.md at the worktree root first —
it is canonical — then the design docs in the order it gives
(design/reactive-system/design.md, state-model.md, component-system.md,
roadmap.md). state-model.md is the primary spec.

State: phases 1–5 and phase 6 slices A1–A4 are complete. A1–A4 were
reviewed, corrected, and committed on 2026-09-22. Gates:
- `just test`: 553 passed, 42 deselected
- `just test-e2e -x -q`: 32 passed, 10 xfailed, 553 deselected
- `just js-tests`: 109 passed, 0 failed
- `just js-build`: green (25.9 KB bundle)
- `ruff check django_glue --select F`: exactly 6 pre-existing findings
  (function.py:5, cursor.py:176, form/mixin.py Any/MutableMapping/BaseModel,
  test_queryset_pagination.py:7); add none
- `git diff --check`: clean

`client_js/dbg_tmp.mjs` is untracked local debug work and was excluded from
the commit. Follow the working rules in this
handoff: do not stage/commit/push/reset without a user request; use Edit/Write
tools for every file edit; add no code comments unless requested; use `just`
for environment-dependent commands; add no legacy wire compatibility.

If asked to verify the tree before a commit, rerun the full gate set:
just test-app django_glue/tests/glue/<touched file> -q   (focused first)
just test
just test-e2e -x -q
just js-tests && just js-build          (only if JavaScript changed)
ruff check django_glue --select F
git diff --check

A5 is not yet authorized. It ports `v1.1/components` onto the settled state
model, migrates the remaining tagged-manifest consumers, and rewrites `docs/`.
Do not merge the component branch mechanically; it targets the old wire format.
Recorded follow-ups include tombstone GC, transient capability capping at
issuance, `$refresh()`, network abort, and keyed-collection reintroduction.
```
