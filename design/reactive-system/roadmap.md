# Reactive System Roadmap

Status: Design gates complete; runtime implemented on `v1.1/base`, consumer migration pending

This document does not itself authorize runtime implementation.

This document owns sequencing, gates, and deferred work. Behavioral contracts
belong in the living design documents.

## Pre-implementation design gates

| Gate | Status | Evidence or remaining work |
| --- | --- | --- |
| Re-express the time-entry dashboard using the new roles | Complete | `state-model.md` §2 reduces thirteen attributes to reconstructors, editable state, independent construction parameters, and derived output |
| Apply the model to every established Glue family | Complete at contract level | `state-model.md` §4 covers models, forms, querysets, formsets, sequences, functions, views, and custom objects |
| Re-check the concrete security findings | Complete at design level | identity locking, callable injection, query controls, TemplateGlue removal, and target-path middleware are settled |
| Walk the thirteen production escape-hatch sites | Complete at design level | questionnaire workflow, chat and notification entity operations, persisted ordering, polling reads, Editor.js integration, and polymorphic notification rendering all fit the shared contracts without retaining a raw transport |
| Resolve state-dependent component questions | Complete at design level | independent policies, transport-only batching, shared-derivation ownership, lifecycle, disposal, configured transient Glue-object results, DOM-bridged declared events, addressed refresh, Django template-tag stamping, typed parameter sources, and bounded per-address policy ownership are settled |
| Name the application authorization contract | Complete at design level | `state-model.md` §3 defines `authorize()` as a pure predicate at three call points, its permissive default, and its per-address denial shape |
| Separate write exposure from read exposure | Complete at design level | `state-model.md` §9 adds the `editable=` projection for model and form adapters, following the established `filters` / `ordering` default contract |
| Separate creation from persisted mutation | Complete at design level | ADR 009 and `state-model.md` §§3–4 add `ADD`, define create-only queryset rows, and preserve secure creation through projected relation querysets without an `allow_create` flag |
| Give batched responses a failure shape | Complete at design level | `state-model.md` §10 scopes faults per address and defines which faults fail the envelope instead |
| Close the child lifecycle | Complete at design level | the "newly introduced" resolution table, reintroduction after expiry, and transient callable results as client-registry bookkeeping rather than signed `children` entries are all settled; the signed map now carries declared children and keyed collection items only |
| Decide the releasable middle | Complete | no compatibility envelope; phases 2–5 are internal checkpoints and consumers migrate once at phase 6 |

## Implementation phases

Server model comes first and the final wire transition comes last, so the two
sides do not move simultaneously. Every phase ends at its gate.

**There is no compatibility envelope.** The legacy `metadata` / `state` /
`manifest_list` wire shapes are being removed, not projected forward, so phases 2
through 5 do not produce a releasable library and their gates are verified against
the branch's own updated suites rather than the shipped 1.0 contract. The branch
diverges from both consuming projects for the duration, and those projects migrate
once at phase 6 rather than incrementally. This is a deliberate trade: maintaining
a parallel envelope through four phases costs more than one coordinated migration,
and the removed shapes are exactly the ambiguity the redesign exists to delete.
Sequencing consequences:

- Phase gates are internal checkpoints, not release candidates. Only phase 1 is
  independently shippable.
- Consumer migration is planned and scheduled as part of phase 6, not discovered
  at it.
- The branch needs its own green suite at every phase, so test migration is part
  of each phase's work rather than deferred to the end.

| # | Phase | Gate |
| --- | --- | --- |
| 1 | Lock identity in `_load_client_state` | The security probe returning `999` for a value signed as `5` returns `5` |
| 2 | Add `parameter=` / `editable=` to `Glue.attr`, the `editable=` projection, and `authorize()`; move derived output to `@Glue.property` | Dashboard and every built-in family map to the three value roles and independent construction-parameter exposure; `editable=` narrows the derived model and form write sets; `authorize()` runs at introduction, reconstruction, and attribute invocation, and a denial blocks the operation without advancing a token |
| 3 | Replace the attribute hierarchy with attribute definitions, explicit namespaces, and addressed children | No attribute subclasses `BaseGlue`; every built-in uses one server pipeline; fluent dotted call paths and non-component children are covered; a projected to-one relation resolves to one shared addressed child across rows; a projected to-many relation preserves the `QuerySetGlue` surface; `ADD` permits creation without mutation of persisted rows; a non-nullable child factory does not run on an owner interaction that does not address it |
| 4 | Introduce schema and split downward data by lifetime | Unchanged field/interface metadata is not resent |
| 5 | Replace the client attribute/proxy caches with one address registry, attribute materializer, child binder, response dispatcher, and role-aware reconciliation | One proxy exists per live address; `ABC` survives when `A -> AB` was sent and `AB` returns; namespace and child paths route to the correct token |
| 6 | Replace response diffs with authoritative addressed snapshots and the flat `objects` envelope | Legacy-object and component E2E tests share the envelope; child entries register before binding; stable child drafts survive owner refresh; replacement/removal disposal passes; a batch with one failing entry advances every other entry unchanged; an unchanged token or `computed_data` is omitted and the client holds its previous value. After consumer migration, the real `stratusadv-portal` time-entry dashboard E2Es cover keyed week navigation and the add-entry modal; no dashboard copy is required in `test_project` |

Phase 1 is independently valuable as a security correction, but runtime work
starts only with explicit implementation authorization.

## Deferred client-runtime work

- **Transport-state bindings.** Glue's client owns loading, pending-call, and
  transport-error status. The exact read-only Alpine interface, trigger versus
  address granularity, delay behavior, and accessibility conventions are
  deferred; these values never enter the policy token.
- **Client-state conveniences.** Application UI state uses ordinary Alpine
  `x-data` in the initial design. A component-level declaration or entanglement
  feature is not planned unless concrete usage demonstrates that Alpine alone
  is inadequate; any future convenience must remain client-only by default.
- **Interval polling.** Periodic refresh uses the ordinary addressed
  request/response and reconciliation contract. Scheduling syntax, visibility
  pausing, disposal, backoff, jitter, and treatment of pending editable updates
  belong to a later client-runtime design.
- **Optimized collection moves.** The canonical ordered-key representation is
  settled. A compact move operation may be added later without changing it.

## Deferred component-model extensions

- **Incremental collection rendering.** Initial component interactions return
  authoritative component HTML, so a growing keyed list may be rerendered and
  morphed in full. Append-only fragments, streamed rows, and partial collection
  rendering may be added later as performance strategies, but must preserve
  address ownership, introduced-object registration, response ordering, and keyed DOM
  reconciliation.
- **Client-evaluated parameters and delayed mounting.** `{% glue_component %}`
  resolves parameters on the server and mounts during the stamping render. An
  Alpine-evaluated parameter source, or `lazy`/`defer` mounting, would each need
  a server-authored capability naming what the client may supply; neither is
  designed yet.
- **Reactive parameter bindings.** Parameters are initially explicit and
  non-reactive. A later declaration may opt a child into propagation from a
  direct parent using selective batching of their independent object entries,
  analogous to Livewire's reactive props.
- **Cascading parameters.** A future Blazor-style provider/consumer mechanism
  may remove repetitive forwarding through deep component trees. It must be
  explicit at both ends, resolve before the descendant token is issued, keep
  the resolved value in that descendant's own signed parameters, and be fixed
  by default. Reactive cascading would be an additional opt-in with bounded
  fan-out. This is a component composition convenience, not a second state
  model and not a replacement for server-side request/service injection.

## Deferred Glue-family extensions

- **Queryset preload.** A queryset introduces no rows; rows answer its queries
  (`state-model.md` §10). A later, explicitly opted-in option such as
  `Glue.queryset(..., preload=True)` may place the first window of rows in the
  introduction for a page that must render them without a round trip. It
  applies only to the queryset that declares it, never to projected relation
  querysets. No consumer needs it as of the 2026-09-22 audit (55 queryset
  registrations across six projects, none eager), so it is not built.

- **Addressed dictionaries.** A future `Glue.dict(...)` shortcut may construct
  a configured, addressed keyed object from a Python mapping. Ordinary values
  would become dictionary-owned state, while configured Glue values would be
  explicit addressed children with independent policies and lifecycle. The
  dictionary's signed schema would define membership and stable child paths;
  refreshable dictionaries would additionally require a declared
  reconstruction provider. This opt-in boundary may support complex transient
  callable results without permitting Glue to recursively discover objects in
  arbitrary dictionaries or other containers. The runtime implementation may
  use a `MappingGlue` class even though the public API is `Glue.dict(...)`.

## Security hardening

These defence-in-depth and operational improvements do not alter the state
roles or wire format and do not gate the redesign:

- [x] Choose and document one policy-token lifetime. **Chosen: 24 hours from
  issuance** (`DJANGO_GLUE_PROXY_POLICY_MAX_AGE_SECONDS = 86400`), fixed rather
  than rolling; a successor token with fresh issuance is delivered only when
  retained values change. See [ADR 013](decisions/013-policy-token-lifetime.md).
  This unblocks the child-reintroduction contract in `state-model.md` §10,
  which depends on a known expiry.
- [ ] Add configurable total-payload, nesting-depth, update-count,
  callable-count, and introduced-object-count limits, including the per-page-render
  introduced-object bound that collections actually exercise.
- [ ] Add the Django system check that fails startup when the `Glue.view`
  response middleware is absent or not last in `MIDDLEWARE`, and the startup check
  that rejects declared event names colliding with standard DOM events.
- [ ] Add throttling and observability for repeated invalid-signature and
  invalid-token requests.
- [ ] Avoid creating persistent sessions solely because an anonymous page
  rendered a Glue object while retaining subject binding where required.
- [ ] Define predictable refresh/recovery after session-key rotation.
- [ ] Provide and document a CSP-compatible Alpine/init path.

Authenticated queryset continuation is not deferred here. Token and
encoded-query size limits before unpickling protect the deserialization boundary
directly and remain part of the state-model implementation.

## Implementation verification checklist

The branch implementation and conformance records for these contracts are in
`STATE_MODEL_HANDOFF.md`. The production-shaped payload measurement and the
security-hardening items above remain separate follow-up work.

- Measure production-shaped policy tokens with retained drafts, queryset
  continuations, and signed collection membership, plus aggregate request size
  under selective batching, before choosing default encoded, decoded, query,
  and batch limits or adopting adaptive token compression. Measure at row scale
  as well as object scale: a hundred-row queryset or formset introduces a hundred
  independently signed children, so the per-page-render bound needs real numbers
  from a production-shaped table, not only from a single object.
- Implement `authorize()` as a pure predicate called at introduction,
  reconstruction, and attribute invocation. Verify it cannot mutate the object, see
  editable updates, or alter the capability, and that a denial produces a
  per-address `not_authorized` entry leaving that address's client state
  untouched.
- Implement per-address response errors and verify the independence invariant
  directly: a batch containing one expired or unauthorized entry must advance
  every other entry exactly as if it had travelled alone.
- Verify the child-slot resolution table: a non-nullable child-producing
  `@Glue.property` must not be evaluated on an owner interaction that does not
  address the child, and a nullable one must be.
- Verify child reintroduction after expiry preserves the proxy, editable draft,
  Alpine scope, and request queue at the same canonical path.
- Verify transient callable results: repeated calls must not grow the owner's
  token; disposing a result client-side must leave no reference that a later
  owner response can trip over; owner disposal must still cascade to results it
  produced; and `effects.dispose` must still tear one down on demand.
- Implement the allowlisting queryset unpickler and verify it rejects a payload
  naming a class outside the published allowlist even when the signature is valid.
- Port the existing `{% glue_component %}` tag to the addressed wire. Verify
  typed Django `FilterExpression` parameters, loop keys, duplicate rejection,
  inherited and included templates, ordinary Django loaders, and stable child
  addresses. Rendered component roots carry address markers; introduced entries
  join the flat `objects` collection.
- Verify declared event delivery after reconciliation and morphing through both
  the source proxy's `$on()` and a rendered component's bubbling `CustomEvent`.
  `Glue.from(element)`, `$glue`, and `component.$el` must all resolve the same
  canonical proxy generation. The tag adds no special event-handler grammar;
  source-scoped `$on()` and ordinary DOM listeners supply event handling.
- Normalize ordinary nested field-path lists and optional `Glue.fields()`
  selections into one signed projection tree for both models and querysets.
  Verify that `__all__`, `select_related()`, and `prefetch_related()` never
  introduce relation traversal; reverse and many-to-many children obey the
  same projection; and separately configured choice sources match an exposed
  relation and its model.
- Introduce a projected to-one relation as an addressed `ModelGlue` child owned
  by the collection, defaulting to `VIEW`, while the relation's raw identity
  stays an editable attribute value on the owner. Verify that two rows
  referencing the same related object resolve to one address and one proxy, that
  disposal follows the collection rather than either row, and that
  `model.parent` and `model.$fields.parent.value` address different leaves.
- Introduce a projected to-many or reverse relation as an addressed
  `QuerySetGlue` child with the normal queryset surface and a signed continuation
  bound to the owner and relation identity. Derive filtering and ordering only
  from projected subfields. Default it to `VIEW`; when the introducing
  capability is at least `ADD`, grant the relation exactly `ADD` so `.new()` is
  available without making persisted members editable.
- Implement `GlueAccess.ADD` in the `VIEW < ADD < CHANGE < DELETE` cascade.
  Verify that an ADD-only queryset exposes existing rows as `VIEW`, creates an
  unsaved ADD draft through `new(initial)`, admits `initial` only against the
  signed editable projection, and transitions that same addressed child to
  `VIEW` after its first successful save. CHANGE and DELETE collections settle
  saved drafts at their corresponding row access. Per-target save admission is
  declared as a callable `required_access` (ADR 010): `ADD` while the signed
  target is unsaved, `CHANGE` once persisted.
- For relation-owned drafts, atomically save and attach through the exact signed
  reverse-FK or many-to-many relation, then reconcile relation membership,
  ordering, annotations, and counts in the same response. Reject an unsaved
  owner and require an explicit callable for through models needing extra data.
- Measure whether a production-shaped queryset continuation justifies
  `scoped-policy.md` Rule 1. Rows keep self-contained policies until it does, and
  must reconstruct through the introducing queryset rather than the default
  manager either way.
- Preserve arbitrary server-authored queryset ergonomics.
- Keep `Glue.attr(...)` state-and-callable only. Compile `Glue.namespace(provider)`
  into root-owned callable paths without giving the provider an address, policy, or
  lifecycle. Read the provider's shape with `inspect.getmembers_static` so a
  descriptor is never triggered during compilation, and bind by ordinary attribute
  access at request time so per-access construction remains the provider's own
  behaviour. Verify against django-spire's `BaseConstructor`: class access,
  instance access, nested providers rebinding to the same `obj`, and the
  constructor's target validation must all be unchanged by the marker.
- Preserve one reactive proxy identity per canonical address.
- Preserve fluent client paths independently of policy boundaries: cover a
  root-owned namespace call such as `model.services.factory.duplicate()`, a
  child non-component call such as `model.form.save()`, and component,
  queryset-row, sequence-item, and callable-result children through the
  same address registry.
- Reject `BaseGlue` values anywhere in parameters, state snapshots, editable
  updates, ordinary derived output, schema values, or event detail. Accept
  them only from declared property/built-in children, addressed keyed
  collections, and authorized callable results; reject raw Django objects and
  arbitrary containers of Glue objects. A future explicit `Glue.dict(...)`
  adapter may introduce an addressed dictionary without weakening this rule.
- Require Glue-object return annotations for child-producing
  `@Glue.property` declarations and direct callable results. Validate the
  configured runtime family and nullability before introducing an address.
- Use `just` for all implementation and verification commands once runtime work
  begins.
