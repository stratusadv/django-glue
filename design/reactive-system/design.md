# Reactive System Design

Status: Accepted living design; implementation pending

This document defines the boundaries and shared invariants of Django Glue's
reactive system. Detailed contracts belong in [`state-model.md`](state-model.md)
and [`component-system.md`](component-system.md).

## Objective

Glue remains a stateless, signed bridge between Django objects and an
Alpine-reactive browser. Components add composition and rendering; they do not
replace the existing model, form, queryset, formset, function, or custom-object
families and do not introduce a second state engine.

## System boundaries

```text
Django declaration
    -> signed policy token + schema + unsigned data
    -> one addressed reactive client object
    -> editable updates and/or a callable invocation
    -> reconstruction, authorization, admission, validation
    -> successor token + unsigned data + result/effects
    -> three-way reconciliation into the same client object
```

HTML is a parallel rendering channel. It may introduce addressed objects, but
the DOM is not the state store and rendered markup is never used to reconstruct
server objects.

## Shared invariants

1. **One state model.** Components and all established Glue families use the
   same roles, capability checks, wire envelope, and reconciliation.
2. **Safe by default.** Server-owned state is not client-writable. Client
   editing is declared rather than assumed, and is admitted and validated rather
   than trusted. Declared values opt in with `editable=True`; Django field
   adapters derive their write set from field metadata and narrow it with an
   explicit `editable=` projection, so read exposure never silently implies
   write exposure.
3. **Signed continuity.** Anything the server will consume from the browser on
   the next request is carried in the signed token. Derived output and schema
   never travel upward.
4. **Current authority wins.** Effective access is the intersection of the
   signed capability, the current declaration, and current application
   authorization. All three are mechanisms, not descriptions: the third is the
   `authorize()` predicate every `BaseGlue` exposes, consulted at introduction,
   reconstruction, and attribute invocation. Its default is permissive by design,
   because inventing an implicit permission convention would be the deny-list
   mistake in another form.
5. **Stable addresses.** A canonical address identifies one live client proxy
   and its request queue. Parameter transitions do not rewrite a
   parent-selected key.
6. **Authoritative responses, local preservation.** The server returns a
   successor snapshot; the client computes the actual patch and preserves newer
   local edits.
7. **Effects and HTML are not state.** Messages, redirects, declared semantic
   events, and fragments have dedicated channels and are never hydrated as
   object values.
8. **Normal Django security paths.** `Glue.view` requests its actual target URL
   through Django's middleware chain. Content negotiation changes only its
   response representation.
9. **One Alpine runtime.** Glue owns a pinned Alpine core and morph runtime;
   consuming projects own optional plugins.
10. **Identity is explicit.** Children and collection items use stable keys,
    never positional identity. Ordered collections canonically store an ordered
    key list and resolve independently addressed children.
11. **Local UI state stays local.** Application-specific transient UI values
    belong to Alpine, while loading and pending-call status belong to Glue's
    client runtime. Neither is signed, hydrated, or declared as server state.
12. **Address ownership governs disposal.** Every live address has one page or
    object owner. Client generations reject late responses after recursive
    teardown; disposal never pretends to revoke a server-valid token.
13. **Refresh is explicit and addressed.** Every addressed Glue object exposes
    the same `$refresh()` operation. Glue refreshes the named object through
    its own token and adapter; it does not infer dependencies from database
    writes or broadcast stringly typed global events. Refresh reads by default
    and submits pending editable updates only under `{submit: true}`, so
    polling never pushes a half-typed draft.
14. **Compute together, own together.** Outputs that require one coherent or
    expensive derivation belong to one addressed object and share ordinary
    private Python memoization there. Transport batching never creates a
    cross-object data context or changes derivation semantics.
15. **Events are declared semantic outputs.** Any addressed Glue object may
    emit a declared, one-shot server-to-client event. Proxy delivery is scoped
    to that source address; a rendered component also emits a bubbling DOM
    `CustomEvent` from its root for ordinary Alpine and JavaScript handling.
    Observing a browser event grants no authority, and any resulting Glue call
    uses that target's own policy.
16. **Parameter sources are visible.** Literal HTML attributes are strings,
    complete `{{ ... }}` attributes resolve typed Django-context values, and
    `:` / `x-bind:` attributes resolve untrusted Alpine values for an
    authorized delayed mount. Glue never guesses between server and client
    scopes, and an admitted mount value becomes an ordinary immutable signed
    parameter.
17. **Component markup is compiled, not interpreted at runtime.** A thin Glue
    `DjangoTemplates` backend compiles registered `<glue:... />` elements once
    into ordinary component nodes while preserving Django's loaders, caching,
    escaping, inheritance, and diagnostics. Templates without Glue elements
    take an unchanged fast path.
18. **Component instances are addressable without global names.** Alpine's
    `$glue` resolves the component for its current scope; `Glue.from(element)`
    resolves the nearest addressed component root in plain JavaScript, and
    `component.$el` returns that root. These mappings follow morph-preserved
    identity and fail after disposal.
19. **Object relationships and reactions are explicit.** A typed
    `@Glue.property` on any addressed Glue object may return a configured Glue
    object and thereby declare a named child address. The child remains the
    sole owner of its state. UI may bind to the reactive child directly; any child outcome that
    should refresh or call the parent is named explicitly by the composition
    code rather than inferred from nesting or database writes.
20. **A Glue object is never an ordinary value.** `BaseGlue` means an
    independently addressed authority boundary. A `BaseGlue` instance cannot
    be a parameter, retained or editable state leaf, ordinary derived output,
    event detail, or an arbitrary item nested inside those values. Configured
    Glue objects travel only as named children, built-in adapter children such
    as a model's configured form or a projected relation, keyed collection
    items, or directly declared callable results, and always own independent
    policies.
21. **Client shape does not imply policy shape.** A dotted client API such as
    `model.services.factory.duplicate()` may be a namespaced callable owned by
    the model, while `model.form.save()` targets a child `FormGlue` with
    its own policy. Both are presented as one natural object graph; the schema
    and signed child reference determine the actual target for each operation.
22. **Attributes are not Glue objects.** Values, properties, callables, fields,
    and explicit callable namespaces are lightweight attributes of one addressed
    object. They contribute to that object's schema, capability, state, and
    output through a shared attribute registry; they do not have addresses,
    policies, reconstruction, or nested `BaseGlue` lifecycles of their own.

## Value roles and construction parameters

| Declaration | Role | Construction parameter | Token location | Client writes |
| --- | --- | --- | --- | --- |
| `Glue.attr(parameter=True)` | reconstructor | yes | `target.parameters` | never |
| `Glue.attr(x)` | reconstructor | no | `state_snapshot` | never |
| `Glue.attr(x, parameter=True, editable=True)` | editable state | yes | `target.parameters` | admitted diff |
| `Glue.attr(x, editable=True)` | editable state | no | `state_snapshot` | admitted diff |
| `@Glue.property` | derived output | no | `unsigned_data` | never returned |

`parameter=True` is independent of the value role. It exposes a declaration to
initial construction and supplies its canonical value through the generated
constructor during reconstruction. `editable=True` selects editable state;
without it, a declared value is a reconstructor. Parameterized values live in
`target.parameters`, while retained non-parameterized values live in
`state_snapshot`.

The deciding test is: **will the server consume the browser-carried value on the
next request?** If yes, it must have signed continuity. If no, the server must
recompute or ignore it.

A Glue-object-typed `@Glue.property` is also the server-owned production point
for an addressed Glue child. An ordinary return value follows the table above;
a configured `BaseGlue` return matching the annotation is registered as a child
and represented by an internal address reference instead of being inserted
into `unsigned_data`. Raw Django models, forms, querysets, and formsets are not
promoted implicitly.

## Transport outline

- Initial introduction: a flat `objects` collection containing `address`,
  `policy_token`, `schema`, and `unsigned_data` for every newly introduced
  address.
- Request: a flat `objects` collection containing `address`, `policy_token`,
  editable `updates`, and optionally one callable invocation per participating
  address.
- Response: a flat `objects` collection containing `address`, successor
  `policy_token`, complete `unsigned_data`, optional replacement `schema`, and
  per-address `result`, `effects`, and component `html` where applicable. A
  declared Glue-object result carries an address resolved from another entry in
  the same collection.
- A successor token and `unsigned_data` are each omitted when they did not
  change, and an omission means *unchanged* while an empty value is
  authoritative and clears. Derived, never declared.
- Every addressed Glue object owns its policy independently. Nested components
  do not embed parent or child policies, and the same rule applies to nested
  models, forms, querysets, formsets, and custom objects.
- Failure is scoped per address. An entry may carry `error` instead of a
  successor token; the addresses beside it in the same envelope advance exactly
  as they would have alone. Only faults that make the envelope itself
  uninterpretable fail the whole request.
- The ordinary interaction sends one per-address request entry. When several
  objects independently participate, the transport batches their entries in one
  HTTP exchange rather than merging their state trees or copying ancestry into
  their tokens.
- Batching reduces HTTP overhead only. Each entry reconstructs and derives as if
  it had travelled alone; bundled and unbundled execution must produce the same
  object result. A later operation that depends on an earlier result requires a
  second request, while a genuinely atomic transition belongs to one callable.
  Sharing derived work is an ownership decision, not a property of transport
  timing.
- `$refresh()` is an ordinary interaction without an application callable.
  Callers and scoped event listeners may schedule it for exact live proxies;
  the initial response protocol has no server-authored refresh-target effect.
- Server-emitted semantic events travel under `effects.events` on their source
  object entry. They are consumed after that response is fully applied and
  never enter the state or authority model. All proxies support source-scoped
  `$on()`; rendered components additionally bridge the event to a bubbling DOM
  `CustomEvent` for Alpine and plain JavaScript.

The token contains subject binding, target parameters, capability,
`state_snapshot`, a shallow `children` path/address map, and temporal
constraints. Signing provides integrity, not confidentiality, freshness,
domain validity, or authorization by itself.

## Ownership of concerns

| Concern | Authoritative document |
| --- | --- |
| Roles, signing, updates, validation, schema, wire format | `state-model.md` |
| Proxy reconciliation and authoritative snapshots | `state-model.md` |
| Components, stamping, parentage, keys, lifecycle | `component-system.md` |
| Alpine startup, morphing, DOM preservation | `component-system.md` |
| Phases, gates, deferred polling and hardening | `roadmap.md` |
| Historical rationale | `decisions/` |

## Production escape-hatch validation

The thirteen direct `Glue.fetch` / `Glue.http.postJson` calls measured across
stratusadv-portal and django-spire are a design gate, not thirteen APIs to
preserve. They are reviewed by behavioral category and then checked at every
concrete site. A category passes only when the shared contract fits each site
without weakening current authorization or forcing established Glue objects
through components unnecessarily.

### Domain workflow: questionnaire

The questionnaire's `next_question` and `submit_answer` endpoints become one
addressed `QuestionnaireGame` component rather than standalone functions. Its
signed `questionnaire_id` parameter selects the workflow. Its
`current_question_id` is bare server-owned state: after an answer is saved, the
database-derived "next unanswered" question changes immediately, while the UI
must continue showing the answered question and its percentages until the user
explicitly advances. `mount()` chooses the initial question,
`submit_answer(choice)` records against the retained question, and
`next_question()` advances it.

Question details, percentages, answer status, and progress are recomputed
down-only properties. Loading, submitting, and temporary selection feedback
remain client/transport state. The client supplies only the annotated `choice`;
it does not supply a `question_id`, and the current request is server-injected.
Every call reauthorizes the signed questionnaire target. This absorbs both raw
requests with the existing parameter, retained-state, callable, injection, and
authoritative-response contracts and adds no new primitive.

### Entity operations: recent chats

The chat rename and soft-delete endpoints remain on the established object
path. A configured `QuerySetGlue` exposes the current user's recent chats, its
child `ModelGlue` proxies expose `name` as an editable field, and the explicitly
declared model method `set_deleted()` is callable with delete access. The
frontend calls `chat.save()` and `chat.set_deleted()` directly, then explicitly
refreshes the owning queryset when soft deletion changes membership. A visual
component may expose that queryset through a property, but it does not proxy
the row operations or duplicate their state.

A queryset-produced row's independent policy must retain the authenticated
scope that introduced it as well as its immutable PK. Reconstructing the row
through the model's unrestricted default manager would discard the queryset's
authorization boundary. Only explicitly declared model methods are callable;
ordinary model methods are never exposed by inspection.

The notification `set_viewed` endpoint is likewise absorbed by an established
Glue object rather than a component wrapper. The configured, user-scoped
`AppNotificationQuerySet` explicitly exposes `mark_viewed(request)` with change
access. It accepts no client IDs, receives the request through server
injection, and operates on its authenticated base queryset. Client-added query
controls do not silently redefine a domain command; acting on a filtered subset
would require an explicitly admitted filter argument. Its response advances
the queryset itself, while any independent badge or component refresh remains
an explicit reaction.

### Persisted ordering

The three knowledge reorder endpoints are persisted domain operations, not
editable collection snapshots. The hierarchical navigation component owns
`move_collection(collection_id, parent_id, position)` and
`move_entry(entry_id, collection_id, position)`, validates both source and
destination inside its authorized tree, persists transactionally, and returns
the freshly derived tree. Its search, expansion, and dragging state remain in
Alpine.

The single-collection entry list instead exposes `reorder(entry_id, position)`
on its configured, authorized `EntryQuerySet`; the queryset itself fixes the
destination collection, so the browser no longer supplies `collection_id`.
The callable's authoritative queryset response carries the new order.

These compact domain commands do not weaken the generic editable-order
protocol. A client-retained ordered collection still submits its complete
proposed key list for admission. Here the database remains canonical, callable
arguments are validated proposals rather than state, and the server re-derives
the authoritative order after committing the move. Generic optimized move
updates therefore remain deferred.

### Polling reads

The notification check and file-conversion refresh require no polling-specific
server protocol. A `NotificationDropdown` component derives the inexpensive
`has_new_notifications` flag and owns a configured notification-queryset child;
polling refreshes only the component address. Marking that queryset viewed and
refreshing the independent indicator remain explicitly sequenced operations.

The converting-files endpoint becomes a read-only `QuerySetGlue` over the
existing `File` queryset with explicitly exposed fields. Its ordinary
`$refresh()` authoritatively adds, updates, and removes keyed row proxies,
eliminating the hand-built JSON string and raw endpoint. Existing timers may
invoke `$refresh()` during migration. Visibility pausing, disposal, backoff,
jitter, duplicate suppression, and public polling syntax remain client-runtime
roadmap work rather than state-model requirements.

### External editor integration

Editor.js block autosave and final tag processing belong to one addressed
`EntryVersionEditor` component. The editor retains its in-progress document as
client/widget state and submits a validated block snapshot to
`save_blocks(blocks)`; the document is not duplicated as editable component
state. `finish_editing(blocks)` transactionally persists the latest supplied
snapshot before recomputing tags, so finalization cannot race an older
autosave. Address ordering sequences already-issued saves and the integration
cancels any not-yet-issued debounce before finalizing.

The signed parameter names an `entry_version_id`, every call resolves it
through current authorization, and structured block input is bounded and
validated while server order comes from list position. Initial blocks travel
in initial render context rather than recurring `unsigned_data`; the
Editor.js-owned DOM is morph-protected. Plain JavaScript resolves the component
through `Glue.from(element)`. Cross-tab overwrite protection may opt into the
state model's authoritative version contract; otherwise last-write-wins is an
explicit domain constraint.

### Polymorphic notification presentation

The notification `render_templates` endpoint exposes a mismatch rather than a
missing HTML-result shape. `QuerySetGlue` currently supplies client-rendered
row data, while each row selects an arbitrary Django template that must be
rendered on the server. Preserving that split would require a second request,
an application-managed HTML cache, keyed result distribution, and manual DOM
insertion. A keyed map of HTML results would package the escape hatch without
removing it.

Notification lists and dropdown contents therefore become render-first
components. The component owns search, ordering, pagination, and the number of
visible rows; its Django template iterates the authorized queryset and includes
each row's server-selected `item.template`. Its normal authoritative HTML is
morphed with stable row keys. The raw render endpoint, `hydrateTemplates()`,
application HTML cache, and `x-html` distribution disappear.

This does not replace the object model with component RPC. The component owns
a configured notification-queryset child, and rendered rows are associated
with that queryset's scoped `ModelGlue` children. The frontend may still call
explicit row or queryset capabilities directly. When such an operation changes
presentation or membership, composition explicitly refreshes the component in
accordance with the relationship contract above.

The initial contract may rerender the growing keyed list when more rows become
visible. Existing row DOM survives the morph. Append-only or streamed
collection fragments are a performance extension, not a prerequisite for
absorbing this escape hatch.
