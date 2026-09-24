# State Model

Status: Accepted living design; implementation pending

Date: 2026-09-10

Refines the state-related portions of [`component-system.md`](component-system.md)
(signed mutable state, the boundary with client-only state, and
`takes_client_state` / `updates_client_state` naming) and adopts
`docs/future/attribute-glue-unification.md`, whose stated precondition —
*"the current attribute confusion causes real bugs"* — is now met.

Evidence: [`research/state-management-audit.md`](../../research/state-management-audit.md)
(catalogue, usage census across django-glue, stratusadv-portal and django-spire,
seven rulings) and
[`research/comparative-analysis.md`](../../research/comparative-analysis.md)
(Livewire/Unicorn comparison and security findings).

---

## Context

Glue moves values between a Django process and a browser through roughly
twenty-two mechanisms, and answers *"what is state?"* in forty-six
implementations: 8 `get_identity`, 8 `_reconstruct_from_policy`, 7 `get_state`,
7 `get_metadata`, 7 attribute `state` properties, 4 `_load_client_state`, and 5
JavaScript `_applyResponseData` overrides.

Three of those are load-bearing defects rather than untidiness:

- **`identity=True` is signed but not enforced.** `_load_client_state` hydrates
  every `StateAttribute`, and `ReadOnlyAttribute` — documented as "read-only
  regardless of the GlueObject's access level" — is a `StateAttribute` subclass.
  A value signed as `5` returns `999` when the client posts it.
- **`_mergeState` deletes keys the server did not send**, so a response
  overwrites whatever the user was editing.
- **Relations default open.** `foreign_key.py` uses
  `fields = self.related_fields or '__all__'`, and `related_set.py` hardcodes
  `fields=ALL_FIELDS`. Without explicit configuration, a related object exposes
  every field; `select_related()` can also turn a loading optimization into
  additional exposure.

Seven of the original component design's ten open questions were downstream of
having no single state model. Thirteen sites in production bypass glue entirely with
`Glue.fetch` / `Glue.http.postJson`, each one a case the proxy system has no
concept for: collection reorder, interval polling, acting on an unregistered
object, and domain RPC that is not model CRUD.

Doing this now rather than incrementally: the public migration surface is two
consuming projects, two component-shaped classes, and two `identity=True` call
sites, but the behavioural surface is every built-in Glue family. Models,
forms, querysets, formsets, sequences, functions, and view fragments must move
through the same state/effect contract; components do not get a parallel
engine. The branch is already spending a breaking-change budget on bundled
Alpine and `renderOuterHtml`'s single-root rule.

---

## Decision

### 1. Three value roles and independent construction exposure

A developer declares what a value **is** and, independently, whether it is a
construction parameter. Direction, protection and timing are what glue derives
from those declarations — they are the maintainer's model (§3), not the public
vocabulary.

| Declaration                                     | Role           | Construction parameter | Signed token location | Client may write | Round-trips |
| ----------------------------------------------- | -------------- | ---------------------- | --------------------- | ---------------- | ----------- |
| `Glue.attr(parameter=True)`                   | reconstructor  | yes                    | `target.parameters` | **no**     | yes         |
| `Glue.attr(x)`                                | reconstructor  | no                     | `state_snapshot`    | **no**     | yes         |
| `Glue.attr(x, parameter=True, editable=True)` | editable state | yes                    | `target.parameters` | yes, admitted    | yes         |
| `Glue.attr(x, editable=True)`                 | editable state | no                     | `state_snapshot`    | yes, admitted    | yes         |
| `@Glue.property`                              | derived output | no                     | no                    | **no**     | no          |

`parameter=True` is not a value role. It exposes that declared value to initial
construction and mounting, and causes its canonical value to be supplied to the
generated constructor during later reconstruction. The value's role still comes
from `editable`: a non-editable value is a reconstructor, while an editable one
is acknowledged editable state. Parameterized values live in
`target.parameters`; non-parameterized retained values live in
`state_snapshot`.

A parameter that selects an authorization-sensitive target normally remains a
reconstructor. Marking a parameter editable is an explicit statement that its
new value is untrusted application input: signing preserves the last canonical
baseline but does not authorize the proposed target or make it safe for domain
use. The same admission, validation, and authorization obligations apply as for
any other editable value.

"Client may write" describes an already-issued object's normal interaction
policy. Construction inputs always come from the server: a Django construction
site or `{% glue_component %}` resolves every parameter before the object is
introduced, and the client never supplies one. Whether later client updates are
allowed is determined by the value's independent editable role.

**The reconstructor role is the default.** A bare `Glue.attr(x)` survives in the
signed policy token's `state_snapshot` and cannot be changed by the client.
`Glue.attr(parameter=True)` has the same role but is supplied through the
constructor. Writability is opt-in, matching the opt-in exposure model that has
kept glue clear of the deny-list CVEs Unicorn has shipped twice.

Role-based opt-in write governs **declared values**. Django field adapters
cannot use the same mechanism, because their leaves are not declared one at a
time — they are projected in bulk from model or form metadata. Those families
therefore *derive* their write set from field metadata and narrow it with an
explicit projection; see [§9&#39;s `editable=`](#9-declaration-api). The guarantee
is the same in both cases — the client cannot write a leaf the server did not
mark writable — but the mechanism differs, and §9 is authoritative for the
adapter half.

An editable value has two representations on a request: its last canonical
value is covered by the signed token, in `target.parameters` when parameterized
and otherwise in `state_snapshot`, while the client's proposed change travels
separately in `updates`. Here, **canonical means the last server-acknowledged
protocol state**. It does not mean that the value passed domain validation, is
safe to use without revalidation, or matches persisted database state. The
signature establishes the baseline; protocol admission decides whether the
update may enter that baseline, while domain validation decides whether an
action may use or persist it.

`@Glue.property` is different from a reconstructor even though both are
client-read-only. A property is recomputed from signed state or another
authoritative source, so the server never consumes the browser's copy. It is
sent downward for display and reconciliation but omitted from signed retained
state. Client-interface metadata is more disposable still: the server ignores
the browser's copy, and it ships downward in `static_data`.

Note the flag is deliberately inverted relative to Livewire. Livewire needs
`#[Locked]` because every public property is client-writable by default; glue
needs `editable=True` because the safe case is the default. The dangerous option
is the one you have to type.

### 2. The test that decides signing

> **Will the server consume the browser-carried value on the next request?**

**Yes** → its last canonical value belongs in the **signed policy token**.
Glue is stateless between requests, so the only place ordinary component memory
can survive is the token the client holds. Parameterized values go in
`target.parameters`; non-parameterized reconstructors and server-acknowledged
editable draft state go in `state_snapshot`.

**No** → it is a **derived output** or construction metadata. The server
recomputes it or ignores it, so authenticity of the browser's copy is
irrelevant because that copy is never read.

A browser-carried value is therefore safe in one of three ways: signed,
admitted as an editable update and revalidated before domain use, or ignored.
`week_of` and `total_hours` look
identical from the browser — neither can be changed directly — but for opposite
reasons. `week_of` is signed because the next request consumes it;
`total_hours` is ignored because the server derives it again.

The role explains who may advance a retained value. A reconstructor is advanced
only by server code; editable state is owned collaboratively through admitted
client updates. The independent parameter declaration explains how the initial
value enters and whether its canonical value is supplied to the constructor on
later requests. An adapter may derive an equivalent parameter from its wrapped
object. `loaded_row_count`, for example, is a non-parameterized reconstructor:
the next batch needs it, but it is internal cursor memory rather than an input
to the component.

**A reconstructor may be advanced by the server, never by the client.** An
editable value may also be a parameter, but its update still travels through
the ordinary admitted update channel. The token is re-signed whenever either
kind advances, so a cursor or a selection stays integrity-protected as it moves
— but re-signing is *derived from whether anything changed*, not performed
unconditionally. See
[§10&#39;s omission rules](#responses-omit-what-did-not-change). Livewire's `#[Locked]` has exactly these
semantics — verified in
`src/Features/SupportLockedProperties/BaseLocked.php`, which hooks the *update*
path only.

#### Worked example: `start_date` was never state

`TimeEntryDashboardGlue` declares thirteen attributes. `_load_week(target_date)`
derives every one of them from two inputs — `user_id` and `target_date` — and
`_reconstruct_from_policy` passes only `user_id`. **`target_date` is never stored
anywhere**; it exists solely as a local variable.

So `previous_week()` has to recover its own input from its own output:

```python
target_date = datetime.date.fromisoformat(self.start_date) - timedelta(days=7)
```

That line reverse-engineers the input from a derived display string, which is
the only reason `takes_client_state=['start_date']` exists — and it ships that
value **unsigned**.

Declaring the missing input fixes it outright:

```python
user_id: int           = Glue.attr(parameter=True)
week_of: datetime.date = Glue.attr(parameter=True)
```

`start_date`, `end_date`, `date_range_display`, `day_collection`, five totals and
three percentages all become derived. Thirteen attributes become **one new
parameter and twelve derived values**, `previous_week()` becomes
`self.week_of -= timedelta(days=7)`, and nothing unsigned goes up.

The lesson generalises: a value that is hard to classify is usually a derived
value standing in for an input nobody declared.

### 3. The internal model: direction, timing, permission

The roles and parameter declaration above are the surface. The model underneath
answers three questions of every value, and this is the vocabulary for
maintainers rather than users:

- **Direction** — which way it travels, and therefore whether it needs signing.
- **Timing** — what causes it to travel: once, whenever it changes, or on demand.
- **Permission** — the `GlueAccess` cascade, the attribute allowlist, and the
  application authorization contract below.

Direction and Timing are independent: a form field's `label` and a component's
`total_hours` both travel down only, but an unchanged label normally ships only
in the initial `static_data` while `total_hours` is recomputed for each authoritative
response. Parameterized values and non-parameterized retained state travel both
ways inside the signed policy token; the editable role adds a separate untrusted
update channel to either location. Neither answer derives from the other, which
is why `updates_client_state` — half a Direction answer with a Timing answer
folded in — reads as confusing.

Permission is asked per value. Authentication — session, user, expiry — is asked
once per capability and stays in the token; conflating them would put one user
binding on every value and reopen the token-size question.

`GlueAccess` is one ordered maximum-capability cascade:

```text
VIEW < ADD < CHANGE < DELETE
```

`VIEW` permits reads. `ADD` additionally permits creation but not mutation of a
persisted target. `CHANGE` includes creation and persisted mutation. `DELETE`
includes all four capabilities. This ordering is Glue's least-authority model,
not a claim that Django's `add`, `change`, and `delete` permissions imply one
another; `authorize()` below remains the application-owned check for those
orthogonal rules. Creation is part of the access cascade rather than a separate
`allow_create` flag (ADR 009).

The target identity chooses the required access. Saving an unsaved model or
model form requires `ADD`; saving one whose signed `target_pk` is non-null
requires `CHANGE`; deletion requires `DELETE`. A client cannot switch branches
by submitting an identity because target identity is reconstructed from signed
policy.

The declaration contract expresses this per-target admission directly:
`required_access` may be a static `GlueAccess` or a callable receiving the
reconstructed target and returning the `GlueAccess` that target requires
(ADR 010). The built-in `save` calls declare the create-versus-persist branch
that way; resolution happens server-side at attribute invocation and
authorization, never from client input.

Timing is deliberately not called "frequency": it describes when a value is
included in an exchange, not how often a client initiates exchanges. Periodic
refresh is object-level client scheduling and is deferred in `roadmap.md`; it
does not add an `ON_INTERVAL` value role.

#### Application authorization is a declared contract, not a property

Effective access is the intersection of three terms: the signed capability, the
current server declaration, and current application authorization. The first two
are framework-owned and fully derivable from the token and the class. The third
is application knowledge — whether *this* user may act on *this* object right
now — and it therefore needs a named contract rather than a described property.

Every `BaseGlue` exposes one:

```python
class GlueOperationKind(StrEnum):
    INTRODUCE = 'introduce'
    REFRESH = 'refresh'
    UPDATE = 'update'
    CALL = 'call'


@dataclass(frozen=True, slots=True, kw_only=True)
class GlueOperation:
    kind: GlueOperationKind
    attribute: str | None       # canonical attribute path, or None for object-level
    required_access: GlueAccess


class BaseGlue:
    def authorize(self, request: HttpRequest, operation: GlueOperation) -> bool:
        return True
```

`authorize()` is a **pure predicate**. It receives the reconstructed object, the
current request, and what is being attempted; it returns a boolean. It may not
mutate the object, may not see or alter editable updates, may not widen or
narrow the capability, and may not change reconstruction order. That is what
distinguishes it from the rejected `hydrate()` / `dehydrate()` / `boot()` hooks:
those interpose on the signed reconstruction pipeline, while this answers one
question at a fixed point in it.

It is consulted at exactly three points, in this order:

1. **Introduction** — before an address is assigned and its first token issued,
   with `kind='introduce'`. A denial means the object is never introduced and no
   token exists for it. A page-root denial is a server-side error in the view; a
   child denial means the owner's declared slot resolves to absent.
2. **Reconstruction** — after the token is verified and the target is
   reconstructed, before protocol admission, with `kind='refresh'`, `'update'`
   or `'call'` as the interaction requires. A denial fails that address's entry
   and issues no successor token.
3. **Attribute invocation** — before each authorized callable runs and before
   each admitted draft is applied, with `attribute` naming the exact path. This is where
   a per-field or per-method rule lives; the object-level check cannot express
   "may read the row but may not call `set_deleted`".

`authorize()` never substitutes for the other two terms, and the other two never
substitute for it. A denial at any point is reported through the per-address
`error` channel in §10 with code `not_authorized`, leaving the client's canonical
data, token, static data and drafts for that address untouched.

**The default is deliberately permissive, and that is a documented choice.** A
bare `BaseGlue` authorizes everything, because the signed capability and the
declared exposure surface are the terms Glue can enforce on the developer's
behalf, and inventing an implicit permission convention would be the deny-list
mistake in a different costume. What Glue guarantees is that the hook exists, is
always called, and is called at points where a denial is still cheap.

The built-in families narrow it where the adapter genuinely knows better:

| Family                             | Default`authorize()`                                                                                                                |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| Custom objects and components      | permissive; the application overrides                                                                                                 |
| `ModelGlue`                      | permissive, but reconstruction refetches through the scope that introduced the row rather than the unrestricted default manager (§4) |
| `FormGlue` / `ModelForm`       | permissive; inherits the model rule for its bound instance                                                                            |
| `QuerySetGlue`                   | permissive; the signed authenticated continuation*is* the scope, and a client query can only narrow it                              |
| `FormSetGlue` / `SequenceGlue` | permissive; delegates to each keyed child                                                                                             |
| `FunctionGlue`                   | permissive; the signed target is the entire capability                                                                                |

A family whose default is permissive is not thereby unguarded — it is guarded by
capability and declaration, and `authorize()` is the seam for the rule only the
application can state. Documentation must say this plainly rather than implying
that signing confers permission.

### 4. Addressed objects and attributes use one pipeline, not one class

`BaseGlue` remains the internal base for an independently addressed Glue
object. Components, models, forms, querysets, formsets, sequences, functions,
and custom objects need an address, reconstruction, a capability, a policy
token, a request queue, and a client lifecycle. A field, value, property, or
callable does not. `BaseGlueAttribute` therefore does **not** become a
`BaseGlue` subclass; the existing attribute hierarchy is removed rather than
promoted.

Declarations compile into a deterministic attribute registry. A lightweight
attribute definition records a complete path, kind, value role where applicable,
construction-parameter exposure, access requirement, getter/setter or callable
target, type adapter, and schema contribution. A bound attribute may pair that
immutable definition with one
`BaseGlue` instance or an explicitly delegated provider, but it does not own
state serialization, metadata envelopes, policy generation, reconstruction,
or a loading lifecycle. Those decisions remain in the shared addressed-object
pipeline and derive from the attribute's role.

This is behavioral unification, not a class collapse:

| Current mechanism                                | Replacement                                                                           |
| ------------------------------------------------ | ------------------------------------------------------------------------------------- |
| `BaseGlueAttribute`                            | removed; internal attribute definition/binding                                        |
| `StateAttribute` / `ReadOnlyAttribute`       | a value attribute with one of the three roles and independent parameter exposure      |
| `CallableAttribute`                            | a callable attribute definition                                                       |
| `ModelFieldAttribute` / `FormFieldAttribute` | value attributes plus Django field adapters and schema projections                    |
| `CompositeStateAttribute`                      | ordinary structured data or an explicit callable namespace; never recursive discovery |
| `GlueObjectAttribute`                          | addressed child registration and an address reference                                 |
| `GlueAttributeCollector`                       | deterministic schema/attribute compilation plus explicit provider binding             |

Composition terminology is exact:

- an **addressed object** is any independently reconstructed `BaseGlue`;
- its **owner** controls where that address is introduced and when its client
  lifecycle ends;
- a **child** is an addressed object introduced and owned by another addressed
  object;
- an **address reference** is a wire pointer to a registered proxy and does not
  create a second owner; and
- a **namespace** is a non-addressed structural grouping of attributes.

Three current tangles then disappear:

- **Mixed grain.** `ModelFieldAttribute.state` currently combines an editable
  `value` and derived `errors` in one object. The attribute's value enters
  `state_snapshot`; its errors enter `computed_data`; its stable interface
  metadata enters `static_data`.
- **Family-specific serialization.** Type adapters encode, decode, coerce, and
  validate leaves without making those leaves independently addressable.
- **Nested timing and authority.** A foreign key's raw editable identity is a
  attribute value. An exposed related `ModelGlue` is a separate child. Eager
  database loading cannot silently turn one into the other.

#### A projected relation is an addressed child

This is the authoritative rule; §9 and `$fields` below describe its two faces.

Naming related scalar leaves in a projection — `project=('id', 'name')`, or the
equivalent `project__id` / `project__name` paths — introduces `project` as an
addressed `ModelGlue` **child**, not a nested structure inside the owner's own
data. The relation's raw identity remains an ordinary attribute value on the owner,
which is what makes the relation editable; the child is what makes it readable as
an object. Both faces exist at once and neither is derived from the other.

A relation child's policy is self-contained — model, key, projection, capability —
and carries **no continuation**. A row's continuation is meaningful because the
developer authored the queryset and it *is* the permission statement. A relation
has no authored queryset, and synthesizing one means Glue inventing a reverse
subquery nobody wrote. The bound comes instead from two properties that already
hold: only the server issues policies, so a client can address only the related
objects actually projected from authorized rows; and `authorize()` runs per
instance on every request, so the application decides whether this user may still
read it.

Read that as a deliberate, reviewable difference from collection rows. The
residual exposure is the replay property the state model already accepts — a
relation policy issued while the user had access stays usable until expiry even
if the row that introduced it leaves the collection. A project needing a hard
bound declares the relation as an explicit child property with its own configured
queryset, which restores a real continuation.

**To-one relation children default to `VIEW`.** Editing requires an explicit
declaration, because a related object referenced by many rows is one shared
address: an edit made through one row is visible in all of them. That is correct
— it is one object — but surprising enough in a table that it must be opted into.

An explicitly projected to-many or reverse relation is instead an addressed
`QuerySetGlue` child and preserves the ordinary queryset proxy surface, including
`all`, `count`, restricted filtering and ordering, refresh, and `new`. Its signed
continuation is the exact relation manager bound to the signed owner identity;
client query controls can only narrow that base and remain limited to the paths
derived from the projected fields.

The relation queryset also defaults to `VIEW`. If its introducing model or
queryset has `ADD` or stronger access, it receives exactly `ADD`, never implicit
`CHANGE` or `DELETE`. Its persisted members therefore remain read-only while
`relation.new(initial)` may introduce one unsaved member. On its first save, a
reverse foreign key injects the owner identity server-side; a many-to-many
relation saves and adds the new target to that exact relation in one transaction.
An unsaved owner cannot expose `new`, and a custom through model needing
additional values requires an explicit callable instead of the generic
operation. Existing related objects still require an explicit declaration to
become editable.

**Ownership and deduplication.** Two rows referencing the same project resolve to
one address and one proxy. The **collection** owns relation children; rows hold
address references, and an address reference does not create a second owner, so
the ownership forest stays single-owner and acyclic. For a standalone `ModelGlue`
the model owns its own relation children.

This is why a child beats a flattened leaf on cost as well as behaviour: a leaf
duplicates the related data on every row, while a child is one entry referenced
many times. Fifty entries across six projects introduce six children, not fifty.

#### Hard composition boundary

A `BaseGlue` instance is never encoded or hydrated as an ordinary value. It
cannot appear directly or recursively in `target.parameters`,
`state_snapshot`, editable `updates`, ordinary `computed_data`, static data values,
or semantic-event detail. Structured values use declared serializer adapters;
they do not use `BaseGlue` merely to obtain grouping or methods.

Configured Glue objects may enter the graph only through an explicit
address-producing route:

1. a typed `@Glue.property` on any `BaseGlue` returns a stable named child;
2. a built-in adapter exposes an equivalent named or keyed child, such as
   a model's configured form, a queryset row, a formset form, or a projected
   relation;
3. an addressed collection exposes stable-key items; or
4. an authorized callable directly returns one declared transient child.

An ordinary `@Glue.property` result is derived output in `computed_data`. A
Glue-object return annotation instead declares a child slot and makes the
property its server-owned factory. Glue requires the result to be `None` for a
nullable slot or a configured, unbound `BaseGlue` matching that annotation,
binds it beneath the canonical property path, and records its address in the
owner's signed `children` map. An unannotated ordinary property that returns a
`BaseGlue` fails loudly rather than changing kind at runtime. A server-internal
helper uses normal Python `@property`, not `@Glue.property`.

Raw Django models, querysets, forms, and formsets are rejected. The public
family shortcuts such as `Glue.model`, `Glue.form`, `Glue.queryset`, and
`Glue.formset` are the preferred configuration boundary. A custom `BaseGlue`
is constructed directly; the existing `Glue.object(request, glue)` helper only
registers an already-configured page root and is not a composite-object
constructor. Arbitrary containers containing Glue objects are rejected
initially; keyed Glue collections use their dedicated addressed adapter.

A list assigned to a `Glue.attr` is route 3 only when its items are meant to be
proxies: it holds Glue objects, or its declaration names a `glue_factory` that
turns raw items such as model instances into Glue objects. Either case becomes
an addressed `SequenceGlue`. Every other list is ordinary serializable state
and never changes kind; a list mixing Glue objects with raw items and no
factory fails loudly. (User decision, 2026-09-22; it narrows the audit's
`glue_factory` "replace" and `value_adapters` "collapse" rulings — the adapter
and `glue_factory` stay.)

Every live address has exactly one lifecycle owner. A page owns its roots; an
addressed object owns children it introduces. Another JavaScript or Python
reference does not become an owner, and one live address cannot be introduced
under two owners. Ownership is an acyclic forest: an object cannot introduce
itself or an ancestor as a child. Parentage controls lookup and disposal, not state ownership:
a parent never embeds the child's token or state, and isolated reconstruction
of either object does not implicitly reconstruct or hydrate the other.

#### Namespaces are not children

A client path does not determine a policy boundary. A path such as
`model.services.factory.duplicate()` may describe a callable attribute at the
complete path `services.factory.duplicate`, authorized and invoked through the
model's policy. The intermediate objects are stable client namespaces, not
Glue objects or state. Conversely, `model.form.save()` may traverse a
child `FormGlue` and therefore invokes `save` with the form's address and
token.

The server must declare callable delegation explicitly with
`Glue.namespace(provider)` and compile the full path into the owning object's
capability. A namespace is a lightweight attribute grouping: it has no address,
policy, state, or lifecycle. `Glue.attr(...)` remains state-only and cannot be
used to smuggle in a service provider. Glue does not recursively walk an
arbitrary Python object graph looking for decorated values or methods. Path
segments are validated, collisions between values, namespaces, callables, and
children fail at schema compilation, and prototype-sensitive or reserved
client names are rejected. This preserves fluent service APIs without making
service containers `BaseGlue` or treating them as state.

**`Glue.namespace` marks an existing declaration; it does not change how that
declaration behaves.** What ADR 004 removes is *automatic discovery* — Glue
walking arbitrary object graphs looking for decorated attributes. The declaration
style itself is unchanged, and the service pattern already in use across
django-spire continues to work verbatim:

```python
class AuthUser(AbstractUser):
    services = Glue.namespace(AuthUserService())
```

The wrapped value is the ordinary class attribute the project already writes. It
is a **prototype, not the live provider**: `BaseConstructor` installs a `__get__`
on every concrete subclass, so `user.services` constructs a fresh
`AuthUserService(user)` on each access, and a nested provider accessed through
another constructor rebinds to the same `obj`. `Glue.namespace` forwards `__get__`
to the wrapped value and adds nothing to it, so class access, instance access,
nesting, and the constructor's own target validation all behave exactly as they do
today.

Across all declaration forms one rule holds: **Glue must be able to name the
provider class without running application code.** The variable form takes it
from the prototype's type, the function form from its return annotation, and the
configuration form from the named attribute's static type. Nothing in schema or
capability compilation depends on executing a body.

Glue needs two things from the declaration and takes each from the place that can
supply it safely:

- **The provider type, statically**, to compile attributes into the owner's schema
  and signed capability. `inspect.getmembers_static` reads the prototype without
  triggering its descriptor, and the prototype's type names the provider class.
  Glue never performs class-level attribute access to discover shape, because a
  descriptor written for instance binding may construct a throwaway target when
  accessed on the class.
- **The bound provider, at request time**, by ordinary attribute access on the
  glued target. Binding is the provider's own business, which is why Glue does
  not construct one.

The wrapped value must therefore be either a **descriptor** — anything defining
`__get__`, which every `BaseConstructor` subclass is — or a **class**, which Glue
instantiates per access with the glued target. A plain, non-descriptor instance is
rejected at declaration: it would be constructed once at import and shared by
every request and every owner in the process, so any per-request value written to
it would leak across users. That rule costs `BaseConstructor` users nothing and
closes the case for providers that are not written that way.

Request access follows the split in `component-system.md`: the **attribute** declares
`request: HttpRequest` and receives it through server injection. A provider bound
to a model instance has no request of its own and does not need one.

#### A namespace that needs construction arguments

The variable form covers providers that bind themselves from the target alone,
which is the overwhelming majority and the entire django-spire service pattern.
A provider that genuinely needs more is declared as a function instead:

```python
class Report(models.Model):
    @Glue.namespace
    def services(self) -> ReportServices:
        return ReportServices(self, region=settings.REPORT_REGION)
```

This is the same shape a child-producing `@Glue.property` already uses — the
annotation declares, the body produces — so it introduces no new concept. The
return annotation is **required**, because it is the only thing that names the
provider class without running the body, and a body returning something other
than the annotated type fails loudly rather than changing the compiled shape at
runtime.

The function is resolved on each namespace access, exactly as the descriptor form
fires on each attribute access, so the two forms have identical lifetime
semantics and neither caches a provider across calls or across requests. Because
the body runs per request, nothing is shared; this is the safest of the three
forms and the only one that needs no declaration-time guard.

A `BaseConstructor` subclass may be used here too, provided it overrides
`__init__` to accept the extra arguments and still passes `obj` upward. In that
case the descriptor never fires — the body is constructing directly rather than
accessing an attribute — so the body is responsible for supplying the target, as
the example does with `self`.

Declare one form or the other for a given name, never both.

#### Marking a namespace at the configuration boundary

A namespace may equally be marked at the configuration boundary, beside the other
exposure decisions. This is the route for a model you do not own, or where the
model class should carry no Glue import:

```python
Glue.model(
    request, 'task', target=task,
    fields=['id', 'title'],
    namespaces=['services'],
)
```

The entry names an attribute that already exists on the target. Glue resolves its
type statically at configuration time and binds it by ordinary access at request
time — the same two steps, with the marker moved off the class.

Declaring on a `BaseGlue` subclass behaves identically and additionally makes
`self.request` reachable, which is a convenience for custom families rather than
the ordinary path.

Only attributes explicitly declared by the provider class are compiled beneath the
`services` path. A provider may itself declare nested namespaces, which is how
`user.services.processor.send()` compiles; nesting resolves statically through
declared namespaces only, is depth-bounded, and a cycle in the provider graph is a
class-definition error rather than a runtime recursion. The provider remains
server-side implementation and never appears in `state_snapshot` or on the client
proxy.

#### Client object graph

The client mirrors the semantic boundary rather than the old attribute class
hierarchy. One address registry owns one stable Alpine-reactive proxy and
request queue per live address. An attribute materializer projects value paths,
field aliases, derived output, callables, and stable namespace objects from
static data. A child binder connects property paths and keyed collection
slots to proxies in the address registry. A response dispatcher registers all
introduced object entries first, applies each successor response to the proxy
for that address, and only then resolves callable results and effects.

Model, form, queryset, formset, sequence, function, and component client APIs
may add family-specific conveniences, but they do not own separate transport,
canonical-state, reconciliation, child-cache, or response-application
engines. Existing machinery such as recursively decoded policies,
`_initializeGlueObjectAttribute`, and per-family child caches is replaceable;
the compatibility goal is the useful object API, not those internals.

#### Existing Glue families use the same model

The three roles and independent parameter exposure apply to every `BaseGlue`
object, not only `Glue.Component`. Adapters decide how to produce and validate
their leaves; they do not define a second transport. `get_identity`, `get_state`,
per-call state filters, and the five JavaScript `_applyResponseData` overrides
collapse into the shared signed state, update, snapshot, effect, and
reconciliation paths.

The policy boundary is an addressed Glue object, not a visual component.
Standalone and nested models, forms, querysets, formsets, sequences, functions,
and custom objects each own an independent token whenever they are exposed as
independent Glue objects. Ordinary leaf values remain within their owner's
token. Object nesting never causes one token to contain another; composition
is represented by stable addresses in the owner's shallow signed `children`
map. Child policies and state remain independent.

| Family                         | Signed policy data                                                                  | Editable updates                                                            | Derived/output channel                                                     | Adapter-specific gate                                                                                                                                                             |
| ------------------------------ | ----------------------------------------------------------------------------------- | --------------------------------------------------------------------------- | -------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Custom objects and components  | parameterized values, reconstructors, acknowledged editable drafts                  | declared`editable=True` leaves                                            | `@Glue.property`, schema, HTML effects                                   | generated construction and addressed lifecycle                                                                                                                                    |
| `ModelGlue`                  | model class, target PK, exposure/configuration, exposed editable values (row baseline plus acknowledged draft overlay) | the`editable=` projection (§9), derived from field metadata when omitted | current persisted read-only fields, annotations, relation children, errors | re-fetch and authorize the model; validate the draft before persistence; define stale-row conflict behaviour                                                                      |
| `FormGlue` / `ModelForm`   | form class, target PK, initial/server state, acknowledged bound-data draft          | enabled exposed fields                                                      | errors, labels, widgets, choices                                           | preserve complete raw bound data for cross-field validation; files need a handler                                                                                                 |
| `QuerySetGlue`               | authenticated query continuation, configuration, cursor and pagination bookkeeping  | declared query controls only                                                | rows, annotations, counts, and keyed child references                      | verify before unpickling through an allowlisting unpickler; bound payload size; close filter/order allowlists; key row construction by the editable projection; preserve batching |
| `FormSetGlue`                | construction rules, stable membership/order, acknowledged form drafts               | keyed form fields and declared collection operations                        | form/non-form errors and keyed child references                            | replace positional identity with keys; preserve management-form invariants                                                                                                        |
| `SequenceGlue`               | reconstructable provider identity and server-owned order when applicable            | declared collection operations                                              | keyed child references                                                     | define reconstruction, membership, and ordering; an empty identity is invalid                                                                                                     |
| `FunctionGlue`               | callable capability and target                                                      | none; call arguments are untrusted inputs                                   | result/effects and parameter metadata                                      | validate arguments and prevent request/context injection                                                                                                                          |
| `Glue.view` and HTML results | none for the fragment transport; introduced objects carry their own signed policies | none unless represented by an addressed object                              | negotiated HTML envelope, introduced object entries, and effects           | request the actual target URL through normal Django middleware; content negotiation grants no authority                                                                           |

Database-derived values do not become retained state merely because their
adapter can expose them. Conversely, unsaved form/model values, formset
membership, and query cursors cannot disappear merely because those families
predate components. The signing test in §2 is applied leaf by leaf in every
row.

Automatic transport starts only after adapter policy exists. A typed child
property, built-in child declaration, addressed collection, or directly
declared callable result may introduce a configured `BaseGlue`, which is
assigned an address and transported through the shared object pipeline. A raw
Django model, queryset, form, or formset is never automatically exposed by
runtime type: Glue cannot infer safe fields, relation traversal, query
controls, callables, or access. The public `Glue.*` family shortcuts are the
preferred policy-construction boundary; otherwise unsupported raw objects fail
serialization loudly.

For Django adapters, retained editable state is an edit buffer, not a claim
about the wrapped object. `FormGlue` retains the form's admitted raw bound data,
including values that fail field, form, uniqueness, or cross-field validation.
Errors and other presentation output are recomputed into
`computed_data`. `ModelGlue` likewise retains an editable draft overlay while
the database row remains the persisted source of truth. The overlay resolves to
the row's current value on every exposed editable path, so the signed snapshot
carries a complete baseline and the client's canonical view is complete from the
token alone. On reconstruction it re-fetches and reauthorizes the row and admits
only the difference between the signed snapshot and the re-fetched row as the
draft for editing; it must validate and authorize again before persistence. A
successful save may normalize values, assign defaults, or advance `target_pk`,
and the successor snapshot rebases the draft to those resulting server values.

#### `$fields` is a client projection

`$fields` remains the explicit form/editing interface used by `ModelGlue`,
`FormGlue`, and each form inside `FormSetGlue`, but it is not another state
tree. The client constructs stable field proxies from schema descriptors whose
`value_path` points at the field's leaf in the assembled canonical view:

```json
{
  "static_data": {
    "fields": {
      "email": {
        "value_path": "email",
        "type": "EmailField",
        "label": "Email address",
        "required": true,
        "editable": true
      }
    }
  },
  "state_snapshot": {
    "email": "not-an-email"
  },
  "computed_data": {
    "fields": {
      "email": {
        "errors": ["Enter a valid email address."]
      }
    }
  }
}
```

That produces two aliases over one reactive leaf:

```javascript
form.email                 // direct value access
form.$fields.email.value   // the same value through the editing interface
form.$fields.email.errors  // computed field output
form.$fields.email.label   // static_data
```

The schema's `editable` flag lets the client render the right interface, but it
is advisory and grants no authority. The server still checks the current
declaration, signed capability, and current authorization. Fixed field choices
live in `static_data`; state-dependent choices and errors live under
`computed_data.fields`; search results remain method results. Updating view
data, state, or computed field output patches the existing field proxy rather
than
replacing it.

For scalar model fields, direct access and `$fields.<name>.value` address the
same leaf. A relation deliberately has two views: `model.parent` is object
access to the related `ModelGlue` child introduced under §4, while
`model.$fields.parent.value` follows its schema `value_path` to the editable raw
foreign key on the owner. This avoids teaching the generic client Django's
`<name>` versus `<name>_id` conventions, and it is why the child may be read-only
while the relation remains editable — they are different leaves, not two spellings
of one. `$fields` itself is never serialized upward.

#### Query capability follows exposed leaves

`QuerySetGlue` remains part of the unified object model. Client-driven
filtering and ordering use a signed positive capability over complete ORM
paths; checking only the first `__` segment is forbidden. This is a data-access
boundary, not merely input validation: result membership, counts, pagination,
and ordering can reveal a field even when its value is never serialized.

By default, Glue derives filter and ordering permission from the complete graph
of exposed concrete scalar and raw-identity leaves. A relation name alone permits
filtering by its exposed raw identity, not traversal into every field on the
related model. Traversal is derived only through explicitly selected nested
field paths. Thus exposing `notification__title` may permit
`notification__title__icontains`, while
`notification__recipient__password__startswith` remains forbidden.

Field exposure does not enable every registered Django lookup. Glue derives a
conservative, type-appropriate lookup set; expensive or unusual transforms and
lookups require an explicit override. Ordering validates the complete path
after removing at most one leading `-`. Random ordering, ORM expressions,
annotations, reverse traversal, and custom transforms are denied unless the
server explicitly declares the exact capability.

The developer may replace either derived set:

```python
Glue.queryset(
    ...,
    filters={
        'name': ['exact', 'icontains'],
        'created_at': ['gte', 'lte'],
    },
    ordering=['name', 'created_at'],
)
```

`filters=None` and `ordering=None` select the derived defaults; empty
collections disable that operation; supplied collections replace rather than
extend the defaults. An explicitly configured hidden path is legal but grants
observational access and must be treated as data exposure during review.

The normalized result is signed independently of row projection:

```json
{
  "capability": {
    "query": {
      "filters": {
        "name": ["exact", "icontains"],
        "created_at": ["gte", "lte"]
      },
      "ordering": ["name", "created_at"]
    }
  }
}
```

The server validates declared paths when issuing the capability, then validates
the signed paths again against current model metadata and framework query rules
on every request. Static data may advertise the resulting query interface but cannot
grant it. These restrictions apply only to client-supplied query controls; the
server-authored base queryset retains its full Django semantics and always
bounds `all`, `count`, `get`, filtering, ordering, and pagination.

#### Creation is an ADD operation on a collection

`QuerySetGlue.new(initial)` requires `ADD` and introduces a relation-owned or
queryset-owned unsaved `ModelGlue`; it does not persist during `new()`. The
draft receives exactly `ADD`, even when the collection has `CHANGE` or `DELETE`,
because no stronger authority is needed before persistence. `initial` is
untrusted input and every key must be admitted by the queryset's signed
`editable` projection before model defaults and validation run.

The public surface adds no creation flag:

```python
Glue.queryset(
    target=Gorilla.objects.all(),
    access=Glue.Access.ADD,
    fields=Glue.fields('id', 'name', skills=('id', 'name')),
)
```

```javascript
const skill = await gorillas[0].skills.new({name: 'Foraging'})
await skill.save()
```

The root ADD queryset also exposes `gorillas.new()`. When creation should exist
only on a relation, the application declares that relation as a typed child
property returning `Glue.queryset(..., access=Glue.Access.ADD)` and keeps the
root at `VIEW`; this uses the existing explicit-child surface rather than a
relation configuration API.

Persisted row access is derived separately from the collection's maximum access:

| Queryset access | Existing row access | New draft access | Access after first save |
| --------------- | ------------------- | ---------------- | ----------------------- |
| `VIEW`        | `VIEW`            | unavailable      | —                      |
| `ADD`         | `VIEW`            | `ADD`          | `VIEW`                |
| `CHANGE`      | `CHANGE`          | `ADD`          | `CHANGE`              |
| `DELETE`      | `DELETE`          | `ADD`          | `DELETE`              |

The successful save advances the same child from `target_pk: null` to the new
signed primary key; it does not replace the proxy or allocate a second address.
For a projected relation queryset, that transaction also attaches the object to
the exact signed relation. The response reconciles that relation's membership,
count, ordering, and annotations in the same exchange, so the application does
not need a separate refresh merely to observe the attachment. Ordinary query
semantics still win: an active client filter may exclude the new persisted row.

Application authorization is checked for both `new()` and `save()`. The
collection's `ADD` capability is necessary but does not imply Django model
permission, tenant membership, or any other application rule.

### 5. The client reconciles signed state and computed data

Taken from Livewire, which got this right:

- `canonical` — last server-acknowledged protocol state
- `ephemeral` — what the user has changed
- `reactive` — `Alpine.reactive(ephemeral)`

The upward payload is `diff(canonical, ephemeral)` — changed paths only. It
becomes a *derived value rather than a decision*, which is what removes
`takes_client_state` entirely.

The response is different: it carries a successor policy token plus
`computed_data`, not a server-computed diff. The token carries parameters in
`target.parameters`, canonical object state in `state_snapshot`, and the
owner's shallow path/address relationships in `children`.
`computed_data` carries the complete current down-only output the server will
recompute or ignore, including derived properties, form errors, query results,
and annotations. Signed state is not duplicated beside the token, and unsigned
output is never carried back to the server.

The client decodes the successor token and assembles the authoritative view from
its exposed parameters, exposed state snapshot, and the response's
`computed_data`. Parameters appear in that view only when deliberately exposed;
being required for reconstruction does not automatically make one reactive.
Whatever the entry does carry is one atomic response for the address. The
decoded `children` map is reconciled by the address registry rather than
inserted into canonical value state.

Either half may be **omitted** when it did not change (§10). An omitted
`policy_token` means the client's held token remains current and its decoded
parameters, state snapshot and `children` map are still authoritative; an omitted
`computed_data` means the previous downward output still stands. The client
assembles the authoritative view from the newest value it holds for each half,
and an entry carrying neither — nor `result` or `effects` — is a no-op rather
than an instruction to clear anything. Omission is therefore distinct from an
empty value, which *is* authoritative and does clear.

"Authoritative" and "canonical" are protocol terms here. For an editable leaf,
they mean Glue has acknowledged the draft and will use it as the next request's
baseline. They do not mean the draft is domain-valid or persisted. For example,
an invalid email may be canonical `FormGlue` state while the bound form is
invalid and the database still contains the previous email.

Because `computed_data` is not returned on the next request, the server still
does not possess the browser's complete previous canonical view and cannot
calculate a true client-relative diff for the whole object. It verifies the
token, reconstructs the target, hydrates state, admits permitted updates,
derives current output, and returns a successor token plus fresh
`computed_data`.

Receiving a response does **not** mean assigning its values wholesale to the
reactive object. Each request retains the canonical data and exact updates it
was sent with. On response, the client performs a three-way reconciliation:

```text
authoritative  = assemble(decode(response.policy_token), response.computed_data)
expected       = apply(request.canonical, request.updates)
server_changes = diff(expected, authoritative)
canonical      = authoritative
reactive       = patch(reactive, server_changes)
```

Using `expected` rather than the pre-request canonical data is what preserves
ordinary in-flight typing. If `A → AB` was sent, the user has since typed
`ABC`, and the server acknowledges `AB`, there is no server change to patch;
the reactive value remains `ABC`, canonical becomes `AB`, and the next request
sends `AB → ABC`.

Glue makes the same-path conflict rule stronger and more explicit than
Livewire's baseline algorithm. Every editable leaf has a client mutation
revision, captured when a request is sent:

- derived output always accepts the authoritative value; the client never holds
  a competing version of a value it cannot write;
- reconstructors always accept the authoritative value;
- an editable value unchanged locally since send accepts a server change;
- an editable value changed locally since send keeps the newer reactive value,
  while canonical still advances to the server value so the edit remains dirty
  for the next request; and
- an intentional reset or replacement must be an explicit effect rather than
  an accidental consequence of merging state.

Absence is a value, and its meaning is per role. Both `state_snapshot` and
`computed_data` are complete rather than differential, so a key missing from the
authoritative view is a removal and `patch` must delete it. That is not a
rehabilitation of `_mergeState`: the removed defect was deleting keys the server
*did not send* from a **partial** response, which silently discarded whatever the
user was editing. Deleting a key absent from a **complete authoritative view** is
the correct reading of the same operation, and the editable-value rule above
still protects a locally changed leaf from disappearing under an acknowledgement.
A removal reaching a locally changed editable leaf follows the same
newer-wins rule and stays dirty until the server accepts its absence.

The guarantee is therefore precise: an authoritative value that acknowledges a sent
update never overwrites later typing, and a same-path server change does not
overwrite a newer editable value unless the response explicitly requests it.
Responses for one address must be reconciled in request order — by
serialization or sequence buffering — so older data can never regress newer
canonical data.

The canonical, ephemeral, and reactive copies in this reconciliation are
copies of Glue values that participate in the server contract. They do not
include application-specific Alpine state such as an open dropdown or active
tab, nor client-runtime metadata such as a pending request. Those values never
enter a policy token, update diff, authoritative snapshot, or server hydration
path.

State reconciliation protects the reactive value; DOM preservation is the
separate, already-settled mechanism in `component-system.md` §6. State changes
reach the DOM through Alpine bindings, while server-rendered replacement uses
`Alpine.morph`, whose spike verifies that local Alpine state, focus, and caret
survive. The response application order is state reconciliation first, then
effects and fragment morphing.

`_state` and `_mergeState` are removed.

### 6. Effects and fragments are separate channels

Messages, redirects, and declared semantic events are consumed once, not state.
HTML fragments may carry newly introduced entries in the shared `objects`
collection. None belongs in the
state tree; they get dedicated keys in the envelope, as Livewire's `effects`
does.

Address disposal is also an effect. A response may include
`effects.dispose` for the responding address itself or addresses it owns when
a nonvisual object is authoritatively removed. Component removal observed
through HTML morphing supplies the same lifecycle signal without a redundant
effect. Disposal is applied after the relevant state reconciliation and DOM
morph, recursively tears down client-owned descendants, and never returns to
the server as state.

Declared semantic events are effects as well. `effects.events` contains the
event name and ordinary serialized detail; its source is the address of the
response entry, so the wire format does not repeat or accept a target address.
After the complete originating response has been applied, the client delivers
each event to listeners scoped to that source proxy generation. An owner may
explicitly expose a declared event from one signed descendant path; delivery
to that owner retains the original source address and does not expose other
descendant events. If the source is a mounted component, it also dispatches a
real bubbling `CustomEvent` with the same name and detail from the component
root. A mounted owner similarly bridges an explicitly exposed descendant event
from its own root. Alpine and plain JavaScript therefore consume component
events through normal DOM event semantics; non-rendered Glue families use the
universal proxy `$on()` API because they have no canonical element.

An event is down-only output: it is not signed into the successor token, is
never hydrated, and grants no authority to a listener. JavaScript may dispatch
a browser event with the same name, so no DOM event is evidence of a successful
server operation. A handler that calls or refreshes another object uses that
target's own policy and passes through its normal admission, validation, and
authorization.

An event is a best-effort notification about one successfully produced
response, not durable messaging or an exactly-once domain guarantee. Events
queued before a failed interaction are discarded. Payloads must contain plain
serializable data; configured Glue objects are introduced through `result`,
where their address ownership is explicit, rather than smuggled through event
detail.

`$refresh()` itself remains an ordinary addressed request rather than an
effect. Refresh does not imply reset and does not bypass reconciliation. A
component refresh includes its rendered HTML; a mounted component reconciles
that HTML with its current root. In particular, a form keeps its admitted
invalid draft, a model keeps its editable overlay while refetching persisted
data, a queryset reruns its authenticated query, and a component recomputes
downward output.

**Refresh does not submit editable updates by default.** `$refresh()` sends the
address and its current policy token and no `updates`; the server hydrates the
canonical draft already covered by that token and recomputes downward output.
Submitting the client's pending edits is the opt-in form:

```javascript
await form.$refresh()                  // read; pending edits stay local
await form.$refresh({submit: true})    // admit pending edits, then re-derive
```

The default matters because `$refresh()` is also the polling primitive. A form
polled every few seconds must not push a half-typed draft to the server on every
tick, have each response acknowledge it as the successor canonical draft, and
recompute validation errors against it — the user would be told to enter a valid
email address while still typing one. Keeping updates out of the default path
also keeps polling free of write authorization, so a `VIEW`-only object can be
polled without its refresh ever entering the admission path.

Neither form is a reset. Pending local edits survive an unsubmitted refresh
through ordinary reconciliation: the response acknowledges the canonical draft
the token already carried, the client's newer reactive value is newer than the
send point, and the newer-wins rule keeps it. Glue deliberately does not
infer these dependencies from ORM mutations. Composition code names the exact
live proxies to refresh directly or reacts to a scoped semantic event; the
initial contract has no server-authored refresh targets, wildcard invalidation,
or framework-owned global event bus. Component `CustomEvent`s follow ordinary
DOM bubbling, and an application may opt into Alpine's `.window` listener.

`Glue.view` is an HTML transport, not another stateful Glue-object family. The
client sends a same-origin request to the actual target URL with a
Glue-specific `Accept` media type. `get(payload)` encodes the merged shared and
per-request payload as query parameters; `post(payload)` sends the merged
payload as JSON with ordinary Django CSRF protection. The target therefore sees
its real path, method, query/body, user, session, and request context.

A Glue response middleware recognizes the negotiated media type and packages
the rendered response as the shared `{is_glue_template_response, html, objects}` envelope. It runs inside the normal Django handler rather than
resolving or calling the target view itself. It must be the final entry in
`MIDDLEWARE`, so every earlier middleware sees the target request and applies
its outward response handling to the final envelope. The media type changes
only the representation: it bypasses no middleware, confers no permission, and
is safe for any browser to request. Initial targets and redirects remain
same-origin.

Three obligations follow from making one URL serve two representations:

- **`Vary: Accept` is mandatory.** The middleware sets it on every response it
  negotiates *and* on every response it passes through on a request that could
  have negotiated. Without it any shared cache — Django's own
  `UpdateCacheMiddleware`, a CDN, a reverse proxy — may store the JSON envelope
  under the page's cache key and serve it to a browser asking for HTML, or store
  the page and serve it to Glue. This is a cache-correctness requirement with a
  cache-poisoning failure mode, so it is part of the contract rather than
  deployment advice.
- **Non-HTML responses pass through untouched.** The middleware negotiates only
  responses whose content type is HTML. A `StreamingHttpResponse` or
  `FileResponse` is returned unchanged and is never materialized — reading
  `.content` on a streaming response raises, and wrapping a download corrupts
  it. A view that already returns JSON, a redirect, or any non-2xx response is
  likewise passed through; the client treats a response without the envelope
  marker as a non-fragment outcome rather than an error.
- **Ordering is enforced by a system check.** "Final entry in `MIDDLEWARE`" is
  a security-relevant constraint and documentation cannot enforce it. Glue ships
  a Django system check that fails startup when its response middleware is
  absent or not last, in the same way the component registry check rejects
  duplicate tag names.

The central `/__dg__/glue_view/` redispatch endpoint,
`ViewFragmentHttpRequest`, and its manual redirect loop are removed. Redirects
instead follow ordinary HTTP semantics and traverse the middleware chain for
each target. Views need no Glue registration or decorator; existing
`Glue.view(url)` ergonomics remain intact.

### 7. Serialization: annotation for *what*, registry for *how*

The declared type hint names the target type; a registry of type handlers
performs the conversion in both directions. Handlers are registerable by
consuming projects over a built-in set covering Django's common types.

This is narrower than annotation-driven *declaration*, which is rejected (§
Rejected Alternatives). `Glue.attr` still declares state explicitly; the
annotation is consulted only to answer "coerce back to what?" A missing
annotation falls back to the registry or leaves the value untouched.

Replaces `GlueResponseJSONEncoder`, the seven attribute `state` implementations,
the client's `parseFieldValue` type special-casing, and hand-written coercion of
the kind in `day.py`
(`datetime.date.fromisoformat(policy.identity['date'])`).

#### The public extension surface

The refactor removes `BaseGlueAttribute`, which consuming projects could
subclass, and replaces it with several internal registries. Their extensibility
differs, and stating it prevents a project from building on an internal seam:

| Seam                                                                    | Status                      | Extended by                                                                     |
| ----------------------------------------------------------------------- | --------------------------- | ------------------------------------------------------------------------------- |
| Serializer registry                                                     | **public**            | registering a handler for a project value type                                  |
| Glue class registry                                                     | **public**            | registering a custom`BaseGlue` family so its objects reconstruct from a token |
| `authorize()` (§3)                                                   | **public**            | overriding on any`BaseGlue` subclass                                          |
| Queryset unpickler allowlist                                            | **public**, versioned | registering custom lookups or expressions                                       |
| Injection registry                                                      | **closed**            | Glue only; its entries are security-relevant                                    |
| Attribute registry, address registry, child binder, response dispatcher | **internal**          | not extension points; shapes may change without notice                          |

A custom Glue family remains a first-class citizen. It declares a `namespace`,
registers with the Glue class registry so a signed token can route back to it,
implements reconstruction from its signed parameters, and otherwise uses the same
attribute registry, roles, capability, and reconciliation as the built-ins. The
built-in families hold no privilege the registry does not grant — which is what
lets django-spire's contributions live outside this repository.

`BaseGlueAttribute` subclasses have no successor and no shim. A project that
subclassed it was extending an internal seam; the replacement for the cases that
motivated it is a serializer handler (custom value representation), a declared
attribute (custom exposure), or a custom family (custom lifecycle).

### 8. Collections get identity and keys

`SequenceGlue.get_identity()` currently returns `{}` and
`_reconstruct_from_policy` returns an empty list, guarded by
`SequenceLazyLoadNotSupportedError`. **A collection cannot be rebuilt at all.**

Collections gain identity like any other object, and items are addressed by a
declared key rather than by position. Two places currently use index-based
naming, both contradicting the component ADR's rule that *"a loop index is never
a key"*:

- `SequenceGlue.from_item_factory` names items `f'{name}.{index}'`
- `FormSetGlue` names nested forms `form_list.{index}` — a wire-format name
  chosen, per its own comment, to dodge a JavaScript property collision

For a stamped component, an address segment combines the registered component
target with its render-site key. A key is either one immutable, key-safe scalar
supported by the serializer registry or a non-empty tuple of those scalars.
Canonicalization preserves type and tuple boundaries rather than coercing to a
display string, so integer `1`, string `"1"`, and composite `(1, "2")` remain
distinct. Mutable containers and Glue or raw application objects are not valid
keys. Human-readable address paths are diagnostic representations; the wire
treats the canonical typed address as opaque and never reparses the display
spelling.

An address and its parameters are signed separately and have independent
lifetimes. A parameter transition never rewrites or invalidates the current
key. An unsaved form may therefore remain at
`invoice_editor[new-7f3a]` when its `target_pk` advances from `null` to `482`;
the existing proxy, Alpine scope, request queue, and DOM identity survive. Only
a later parent render can remove that address and stamp a child under another
key. If it chooses `482` instead of `new-7f3a`, that is an explicit replacement,
not a state transition inferred by Glue.

An ordered collection is represented canonically as an ordered list of stable
child keys. The children themselves are not embedded positionally: each has an
independent address and policy. For example:

```json
{
  "state_snapshot": {
    "entries": ["entry-471", "entry-482", "entry-503"]
  }
}
```

Those keys resolve `dashboard.entries[entry-471]` and its sibling addresses.
The list's set expresses membership and its positions express order, while a
reorder changes no child address or proxy. The client projects the keys into an
ordered array of child proxies and renders reorderable collections with keyed
`x-for`, not HTML morphing.

The key list belongs in `state_snapshot` only when the server will consume it
on the next request. A query- or database-derived display order that the server
will recompute is downward-only output instead. Server-owned ordering remains
non-editable; an explicitly editable ordering uses the same canonical,
ephemeral, and reactive reconciliation as any other editable state.

The initial editable-reorder protocol submits the complete proposed key list.
Protocol admission rejects duplicates, unknown keys, size violations, and—for
a reorder-only capability—any missing or added membership. Adding and removing
children are distinct declared collection operations with their own
authorization and lifecycle rules. A future move operation may reduce payloads
for very large collections, but it must resolve to the same ordered-key
canonical representation.

Ordering is designed into the contract but need not ship in the first release
(ruling 6). Periodic refresh is a separate client-runtime scheduler around the
ordinary addressed request and reconciliation contract; its detailed behavior
is deferred in `roadmap.md`.

#### The collection forms each child's address

A collection introduces its keyed children. Each child has a **key** — its
stable slot in the collection — and an **address** — its full wire identity.
The key is a signed field of the child's token, supplied by the collection; it
is never an attribute of the item object (ADR 011). The address is the
collection's own address with the child's key appended, so only the collection
can form it: it alone knows its own address. The collection
records the `{key: address}` pairs in its signed `children` map, and the client
registers one proxy per child address.

```
        ┌────────────────────────────────────────────────────┐
        │  COLLECTION — queryset "entries"                   │
        │                                                    │
        │  own address   dash#7f3a9c21.entries               │
        │  children map                                      │
        │    "471" → dash#7f3a9c21.entries[471]              │
        │    "482" → dash#7f3a9c21.entries[482]              │
        └────────────────────────────────────────────────────┘
              │  builds child · assigns key · forms address
              ▼
        ┌────────────────────────────────────────────────────┐
        │  CHILD — one row (a ModelGlue)                     │
        │                                                    │
        │  key       "471"                  ← assigned       │
        │  address   dash#7f3a9c21.entries[471]   ← formed   │
        │                                                    │
        │  knows its key; cannot compute its own address     │
        │  (that needs the collection's address, above)      │
        └────────────────────────────────────────────────────┘
```

Per request the collection builds each live child from its current source
(the current batch, the current forms, the current items), assigns each its
stable key (row PK, form membership key, or item key), forms each child's
address as `collection_address + "[" + key + "]"`, and records the `{key: address}`
pairs in its signed `children` map. The collection and each child are emitted
as separate first-class entries in the `objects` collection. On a later request
it re-derives and verifies each child address from the key (signed in the
child's token), so a child whose key is unchanged keeps its address and proxy.
The client reads the `children` map, registers one proxy per child address, and
pulls each child's own entry from the `objects` collection.

#### Address separator scheme

An address is composed of segments separated by one character per role:

| Role                               | Separator | Example                              |
| ---------------------------------- | --------- | ------------------------------------ |
| Top-level (name + opaque)          | `#`       | `dash#7f3a9c21`                      |
| Named child (owner + path)         | `.`       | `dash#7f3a9c21.entries`              |
| Keyed item (collection + key)      | `[ ]`     | `dash#7f3a9c21.entries[471]`         |
| Related PK (relation + PK)         | `:`       | `dash#7f3a9c21.entries.project:42`   |

The `[ ]` holds the canonical key: scalars bare (strings quoted), tuples
parenthesized (string elements quoted):

```
entries[471]          integer 471
entries["471"]        string "471"   (quoted — else identical to the integer)
entries[(471,42)]     tuple of two ints
entries[(471,"42")]   tuple with a string element
```

The address is opaque; the client never reparses the display spelling.

### 9. Declaration API

`Glue.attr` keeps its name — it is established and familiar. Internally it
dispatches to separate value and callable descriptors instead of one class
branching on `_is_decoratable`. It never declares a provider: service
composition uses `Glue.namespace(...)`, and `Glue.attr` remains state-and-callable
only (ADR 004).

Its five value and callable forms are therefore:

| Form                                            | Declares                      |
| ----------------------------------------------- | ----------------------------- |
| `Glue.attr(parameter=True)`                   | a parameterized reconstructor |
| `Glue.attr(x)`                                | an internal reconstructor     |
| `Glue.attr(x, parameter=True, editable=True)` | parameterized editable state  |
| `Glue.attr(x, editable=True)`                 | internal editable state       |
| `@Glue.attr(required_access=...)`             | a client-callable attribute   |

The callable form is the one the role table in §1 does not cover, because a
callable is not a value and has no direction, timing or signing answer. It is
listed here so the declaration surface is documented in one place rather than
inferred from examples.

`required_access=` on the callable form accepts either a static `GlueAccess` or
a callable of the reconstructed target returning the `GlueAccess` that target
requires — the declaration-level form of the "target identity chooses the
required access" rule in §3 (ADR 010). Static values stay the common case;
callables are for attributes whose gate differs by signed target, such as
`save` (create versus persist).

```python
class TimeEntryDay(Glue.Component):
    template = 'time_tracker/component/day.html'

    date: datetime.date = Glue.attr(parameter=True)
    user_id: int = Glue.attr(parameter=True)
    loaded_row_count: int = Glue.attr(0)
    note: str = Glue.attr(
        '',
        parameter=True,
        editable=True,
        access=GlueAccess.CHANGE,
    )

    @cached_property
    def _entries(self) -> list[TimeEntry]:
        return list(TimeEntry.objects.filter(user_id=self.user_id, period=self.date))

    @Glue.property
    def total_hours(self) -> float:
        return sum(entry.allocated_hours for entry in self._entries)
```

`ModelGlue` and `QuerySetGlue` use one explicit field-projection graph.
`fields` continues to accept its ordinary list of strings, including complete
Django-style relationship paths:

```python
Glue.model(
    ...,
    fields=[
        'id',
        'description',
        'project__id',
        'project__name',
        'user__id',
        'user__first_name',
    ],
)
```

`Glue.fields()` is optional construction sugar for the same selection; it does
not introduce a second field representation or require callers to replace
ordinary lists:

```python
Glue.model(
    ...,
    fields=Glue.fields(
        'id',
        'description',
        project=('id', 'name'),
        user=('id', 'first_name'),
    ),
)
```

The helper returns an immutable selection that normalizes to the same canonical
paths stored in policy. Nested helpers express deeper finite projections, and
`exclude` accepts the same ordinary paths or optional helper. A relation name
alone exposes only its raw identity or to-many membership; related scalar
leaves require explicit subpaths.

Naming related scalar leaves does not flatten them into the owner's data. It
introduces the relation as an addressed `ModelGlue` child under the rule in
§4, read-only unless explicitly declared otherwise, while the relation's raw
identity remains an editable attribute value on the owner. The projection therefore
decides *what the child exposes*, not whether a child exists. `fields='__all__'` means all safe local
concrete fields and raw forward-relation identities, never recursive relation
traversal. `select_related()` and `prefetch_related()` affect loading only and
cannot add exposure.

Naming subfields beneath a to-many or reverse relation introduces an addressed
`QuerySetGlue` child instead. It exposes the normal queryset client surface and
uses only those projected subfields to derive its row, editable, filter, and
ordering capabilities. Access level never widens that field graph.

#### Write exposure is a separate projection from read exposure

`fields` answers "what may be read." It must not also answer "what may be
written," because the two sets differ constantly: a row's `id`, `created_by` and
`invoice_number` are routinely displayed and never client-editable. A developer
who adds a field so it renders should not thereby make it writable.

`editable` is therefore its own projection over the exposed paths, and it follows
exactly the `filters` / `ordering` contract already established for
`QuerySetGlue`:

```python
Glue.model(
    ...,
    fields=Glue.fields('id', 'description', 'allocated_hours', project=('id', 'name')),
    editable=['description', 'allocated_hours'],
)
```

- `editable=None` (omitted) selects the **derived default**: the exposed paths
  whose Django field metadata reports `editable`, intersected with the object's
  access level. This is current behaviour, so existing declarations keep working.
- The access intersection is target-sensitive: `ADD` admits editable draft
  values only while the signed `target_pk` is null. The same ADD-only adapter
  has no writable paths after persistence; its successor is `VIEW`.
- `editable=[]` disables client writes entirely while leaving the object readable.
- A supplied collection **replaces** the derived set rather than extending it,
  and every entry must name an exposed, concrete, Django-editable leaf. A path
  that is not exposed, not concrete, or not editable is a declaration error at
  construction, not a silently dropped entry.
- A raw forward-relation identity is named by its exposed path; making
  `project` writable does not make any leaf *inside* `project` writable.
- `FormGlue` derives its equivalent set from enabled, non-disabled form fields
  and accepts the same explicit narrowing. The form's own `disabled` flag remains
  authoritative when it is stricter.

The signed capability carries the normalized result, and the server revalidates
it against current model metadata on every request, exactly as the query
capability does. Static data's per-field `editable` flag continues to describe the
interface for rendering and continues to grant nothing.

The derived default is retained knowingly: `field.editable` is the closest thing
Django offers to an authored statement of writability, and inverting the default
would break every existing declaration to protect against a mistake the explicit
projection now makes easy to prevent. Documentation must state that the default
is derived rather than closed, so that a project handling sensitive rows knows to
supply `editable=` deliberately.

`related_field_config` is removed. Its projection concern belongs to `fields`,
while its unrelated choice-query concern becomes a separate mapping:

```python
Glue.model(
    ...,
    fields=Glue.fields(
        'id',
        project=('id', 'name'),
    ),
    choices={
        'project': Glue.choices(
            Project.objects.filter(is_active=True),
            search_fields=['name'],
            fields=['name', 'code'],
        ),
    },
)
```

Each choice source must name an exposed relation and query its related model.
Its authenticated continuation remains signed. A `ModelForm` normally obtains
this boundary from its configured form-field queryset; the explicit mapping is
available for direct model editing and deliberate overrides.

**The omitted case is closed by construction rather than by an allowlist.** An
exposed, editable relation with no entry in `choices` gets an implicit source
with three properties:

1. **Label and identity only.** The wire carries `{value, label, obj}` per
   choice, where `value` is the relation's exposed raw identity, `label` is the
   related instance's `__str__`, and `obj` is `{pk, __str__}`. No other related
   field is projected, so the implicit source cannot leak a field that `fields`
   did not expose.
2. **No server-side search.** The implicit source accepts no search argument.
   The server returns one bounded page of choices and the client filters the
   labels it already holds. Because no client string reaches the ORM, the
   relation-traversal oracle that `filters` has to defend against cannot exist on
   this path at all — which is why the default is safe without an allowlist.
3. **Bounded, and loud at the boundary.** The page is capped at the configured
   search limit. A related table larger than the cap is a declaration error
   naming the relation and directing the developer to `Glue.choices(...)` with
   explicit `search_fields`. Glue does not silently truncate a choice list, and
   it does not silently promote client-side filtering into a server query.

Relying on `__str__` is a deliberate trade: it is the one label Django models
reliably author, and it is already what `ModelChoiceField` renders. A `__str__`
that embeds a value the projection excluded is an application disclosure decision
and must be treated as one during review — the same standing §4 gives an
explicitly configured hidden filter path.

Configuring `Glue.choices(...)` opts into the server-side path and its
allowlisted `search_fields`, which remain validated against the related model's
exposed leaves on every request. `search_fields` defaults to `fields` when
omitted, and an unfiltered load of a searchable source returns its first
`search_limit` rows in queryset order, so a plain select populates without a
search. Each choice's `obj` carries `pk`, `__str__`, and the configured
`fields`.

`Glue.choices(..., label_formatter=...)` renders each choice's `label`
server-side from a function taking `(instance)` or `(request, instance)` and
returning a string (rendered as a Django template) or a `TemplateResponse`. The
formatter is accepted as a callable or dotted path but always stored as its
dotted path, so only a string travels inside the signed choice query and the
allowlisting unpickler never admits a function reference; a callable that
cannot be re-imported from its own path, such as a lambda or closure, is a
declaration error. Formatted choices carry `has_html_label: true`, and the
client's `choiceLabelHtml()` passes those labels through while escaping every
other label; `choiceLabelText()` strips markup for text-only contexts.

`Glue.event()` declares a semantic server-to-client output on any `BaseGlue`
family. Calling the bound descriptor appends an event to the current successful
response; it is not a client-callable capability and carries no retained
value:

```python
class EntryEditor(Glue.Component):
    saved = Glue.event()

    def save(self) -> int:
        entry = save_entry(...)
        self.saved(pk=entry.pk)
        return entry.pk
```

Event names appear in down-only schema so composition bindings and direct
`$on()` subscriptions can reject unknown names. Event detail is serialized as
ordinary output and is neither accepted from the client nor inferred from a
callable's name. Built-in adapters may declare documented semantic events when
success has one unambiguous meaning.

**Derived values are `@Glue.property`** — a declaration that already exists with
20 production uses.

Livewire enforces the same line structurally rather than with a flag: its
hydration snapshot is built by `getPublicPropertiesDefinedOnSubclass`, which
reflects and filters to `isPublic() && !isStatic() && isDefault()`, while
`#[Computed]` decorates a *method* (`BaseComputed::evaluateComputed()` invokes
it, and calling it directly throws). A computed value is therefore never a
public property and never persisted in Livewire's hydration snapshot. Glue
copies that boundary selectively: a derived property's evaluated value appears
in `computed_data` sent downward, but never in the signed `state_snapshot` sent
back. Where several derived values share
expensive work, the sharing
is a private `cached_property`: plain Python, invisible to glue, and it removes
the need for a `derive` hook or `computed_attributes` entirely.

```python
class TimeEntryDashboard(Glue.Component):
    user_id: int           = Glue.attr(parameter=True)
    week_of: datetime.date = Glue.attr(parameter=True)

    @cached_property
    def _period(self) -> TimeEntryPeriod:        # one query, shared
        start, end = get_week_boundaries(self.week_of)
        return TimeEntryPeriod(start, end, user_id=self.user_id)

    @Glue.property
    def total_hours(self) -> float:
        return self._period.total_hours

    def previous_week(self) -> None:
        self.week_of -= datetime.timedelta(days=7)   # server advances a parameter
```

A bare `Glue.attr(x)` remains legitimate for a reconstructor that is not
derivable — an external call cached deliberately, or an accumulating counter.
Unlike a property, it survives in the signed `state_snapshot` because the
server consumes it on the next request. Prefer `@Glue.property` whenever the
value can be recomputed from parameters, another reconstructor, or another
authoritative source.

A parameterized declaration with no default is a required constructor argument.
A parameterized declaration with a default is optional, regardless of whether
its role is reconstructor or editable state. The constructor is generated from
those declarations, so the hand-written `__init__` that
`TimeEntryDashboardGlue` carries for thirteen attributes goes away.

Deleted: `takes_client_state`, `updates_client_state`, `LoadingStrategy`,
`identity=True`, `computed_attributes`, and the proposed `derive` hook.

**This also dissolves "optional parameters"** from the component ADR. That
concept existed so a parent could pass preloaded data and save child work, but
it gives a value two incompatible lifetimes: present at mount and absent during
reconstruction. Shared derivation instead follows the ownership boundary:
outputs that require one query remain on one addressed object and share a
private `cached_property`, while template partials or keyed Alpine regions
divide their presentation. An independently addressed child derives from its
own signed parameters. Batching is transport-only and must not silently sign a
large derived result into every child token, reintroduce an optional
construction input, or make results depend on which requests were coalesced.

### 10. Wire format

Conceptual decoded policy-token payload:

```json
{
  "protocol_version": 1,
  "subject": { "session_id": "9a73f51d8c2e4b29", "user_id": 184 },
  "target": {
    "namespace": "time_tracker",
    "address": "dash#7f3a9c21",
    "parameters": { "user_id": 184, "week_of": "2026-09-07" }
  },
  "capability": {
    "access": ["read", "update", "call"],
    "allowed_attributes": ["note", "loaded_row_count", "total_hours"],
    "callables": {
      "save_note": { "allowed_arguments": [] },
      "refresh_entries": { "allowed_arguments": ["force"] }
    }
  },
  "state_snapshot": {
    "note": "Waiting for the customer to confirm scope.",
    "loaded_row_count": 14
  },
  "children": {
    "entry_form": "dash#7f3a9c21.entry_form"
  },
  "temporal": {
    "issued_at": "2026-09-10T16:42:18Z",
    "expires_at": "2026-09-10T17:42:18Z",
    "authoritative_version": 37
  }
}
```

The `address` and the `dispose` path above are shown in their opaque wire form on
purpose. An address must not be derived from parameter values: `week_of` advances
every time `previous_week()` runs, and §8's rule that a parameter transition
never rewrites an address would be violated by any spelling that embedded one.
Human-readable forms such as
`dashboard.TimeEntryDay[(184,2026-09-09)]` exist only in diagnostics and error
messages; nothing on the wire produces or reparses them.

`state_snapshot` is a point-in-time copy of non-parameterized retained state the
server must hydrate on the next request. It contains internal reconstructors and
server-acknowledged editable drafts, which may be domain-invalid. Parameterized
values remain in `target.parameters` whether their role is reconstructor or
editable state; derived output is recomputed and appears only in downward
`computed_data`. `children` is the owner's shallow, signed mapping from canonical
child paths to addresses. It carries no child policy or state. Attribute roles
and parameter exposure are not repeated beside each value: the current server
declaration defines both, and the capability narrows what this client may
access. The effective update permission is the intersection of the current
declaration, the signed capability, and current application authorization.

Adapters may derive and advance their non-editable parameters. A new `FormGlue`,
for example, issues `target_pk: null`; after a successful create it issues a
successor token with the saved instance's PK. That is a server-authored
reconstructor transition, not an editable-state update. The Glue address and
any parent-selected key remain stable across it; they are not recomputed from
the new parameter value.

The construction site supplies parameters explicitly for every Glue family.
After a nested object is introduced, its independently signed parameters do
not remain implicitly bound to the parent expression that originally supplied
them. A changed parent expression therefore does not rewrite the child's
token. Reactive parameter propagation and ambient ancestor lookup are separate
future composition features, not hidden behavior of `parameter=True`.

There is no delayed introduction. An object is introduced complete, during the
server render or response that constructs it, and no global client API may
construct an arbitrary registered component. Client-evaluated construction
inputs and `lazy`/`defer` mounting would each need a server-authored capability
naming what the client may supply; neither is designed (`roadmap.md`, deferred
component-model extensions).

There is likewise no lazy loading. Every introduced entry is a complete first
snapshot: its signed token carries parameters and retained state, and its
`computed_data` carries the object's derived output. No per-object loading
strategy withholds `computed_data` at page load, and no separate `load_state`
fetch fills it in later. Re-deriving an object's output on demand is
`$refresh()` (§6), an ordinary addressed request.

A queryset's rows are the one output that waits, and they wait by the family's
contract rather than by a loading option: rows are the answer to a query. A
queryset's introduction carries its token, schema, callables, and query
controls but no rows; its query callables return rows (with their annotations,
counts, and keyed child references) and introduce each row as a child entry.
This bounds page-load work where it matters: a projected to-many relation is
itself a queryset, so a list of rows does not run and ship every row's related
rows at render. `$refresh()` on a queryset re-runs its signed last query over
the window already loaded, so a refresh never silently shrinks or resets a
scrolled or paged list. Formset forms and sequence items are not query answers
and ship with their collection.

Page load:

```json
{
  "objects": [
    {
      "address": "dash#7f3a9c21",
      "policy_token": "...",
      "static_data": {
        "events": ["saved"],
        "children": {
          "entry_form": { "kind": "form", "nullable": false }
        },
        "fields": {
          "name": {
            "value_path": "name",
            "type": "CharField",
            "label": "Name",
            "editable": true
          }
        }
      },
      "computed_data": { "total_hours": 8.5 }
    },
    {
      "address": "dash#7f3a9c21.entry_form",
      "policy_token": "...",
      "static_data": { "fields": {} },
      "computed_data": { "errors": {} }
    }
  ]
}
```

Request:

```json
{
  "objects": [
    {
      "address": "dash#7f3a9c21",
      "policy_token": "...",
      "updates": { "note": "Rewrote the parser" },
      "call": { "attribute": "save", "kwargs": {} }
    }
  ]
}
```

Response:

```json
{
  "objects": [
    {
      "address": "dash#7f3a9c21",
      "policy_token": "...",
      "computed_data": {
        "total_hours": 9.0
      },
      "result": {},
      "effects": {
        "messages": [],
        "redirect": null,
        "events": [
          { "name": "saved", "detail": { "pk": 471 } }
        ],
        "dispose": ["dash#7f3a9c21.entry_forms[b81e04]"]
      }
    }
  ]
}
```

The policy token signs the subject, target parameters, capability,
`state_snapshot`, shallow `children` map, and temporal constraints as one
envelope. The request does not submit retained values as mutable fields; it
submits the signed token and a client-computed `updates` diff containing
editable paths only. After verifying that the outer request address matches
the signed target, Glue reconstructs the target from signed parameters, hydrates
retained values from `state_snapshot`, performs protocol admission on
`updates`, applies admitted drafts, invokes the action, and issues a new token.
This order is framework-owned and exposes no public hydrate, dehydrate, or
per-request boot hook. Custom serialization and server dependency injection
use their dedicated contracts rather than lifecycle interception.

#### Failure is per address, not per request

A batch is specified as strictly independent: every entry reconstructs, admits,
authorizes and advances against its own address, and bundled execution must
produce the same result as unbundled execution. That invariant is unimplementable
unless one entry can fail without disturbing another, so the envelope carries
failure per address:

```json
{
  "objects": [
    {
      "address": "dash#7f3a9c21",
      "policy_token": "...",
      "computed_data": { "total_hours": 9.0 }
    },
    {
      "address": "dash#7f3a9c21.entry_form",
      "error": { "code": "policy_expired", "message": "..." }
    }
  ]
}
```

The boundary between the two failure scopes is exact:

- **Envelope faults fail the whole request** and return the existing
  whole-response error shape with no `objects` collection. These are faults that
  make the request uninterpretable or unsafe to begin: malformed body, invalid
  content type, CSRF failure, exceeded encoded/decoded/batch bounds, duplicate
  addresses, and an outer address that does not match its signed target.
- **Address faults fail one entry.** These are faults attributable to one
  target: bad signature, expired policy, subject or session mismatch, adapter
  reconstruction failure, protocol admission failure, and authorization denial
  (§3).   The entry carries `error` and carries no `policy_token`, `static_data`,
  `computed_data`, `result` or `effects`.

An entry carrying `error` leaves that address's client-side canonical data,
policy token, static data and editable drafts **exactly as they were**, does not
advance its generation, and rejects the promise of whatever operation targeted
it. It is not a state transition, so it never participates in reconciliation.
Other entries in the same envelope apply normally, which is what preserves the
independence invariant.

Error codes are a closed, documented set. `not_authorized` and `policy_expired`
are distinguished because their client-side remedies differ: the first is
terminal for that operation, while the second is recoverable by reintroduction
(§Reintroducing an expired child).

`objects` is a flat transport collection, not an ownership tree. The static data
declares each fixed child slot and whether it is nullable; collection and
callable schemas declare their keyed or transient child mechanisms. The owner's
successor token supplies the authoritative current path/address binding. The
same child address may be referenced by successive owner tokens without being
included as a response entry again. That repetition neither advances nor
reconciles the child. A child response entry appears only when that child was
newly introduced or independently participated in the interaction.

#### What "newly introduced" means on a stateless server

Glue holds nothing between requests, so "already live" cannot be server memory.
It is read from one authoritative source: **the `children` map inside the
verified incoming token is the owner's live child set.** A first render has no
incoming token, so every declared slot is new.

The consequence worth stating is what the server is therefore *not* required to
do. Child slots are declared statically — the return annotation of a typed
`@Glue.property`, a built-in adapter's named child, a keyed collection's item
family — and that declaration is available from schema compilation without
running any application code. The server compares declared slots against the
incoming live set **before invoking any factory**, and resolves each slot one of
four ways:

| Slot state                                      | Factory runs          | Response entry        | Successor`children`  |
| ----------------------------------------------- | --------------------- | --------------------- | ---------------------- |
| Absent from the live set                        | yes                   | yes, newly introduced | new address            |
| Live, not participating in this interaction     | **no**          | no                    | address copied forward |
| Live and independently participating            | yes, on its own entry | yes                   | same address           |
| Live but listed in the request's`reintroduce` | yes                   | yes, reintroduced     | same address           |

The second row is the important one. A child-producing `@Glue.property` is a
**factory for introduction, not a derivation**: `ChatPanel.chats` does not
construct its queryset, evaluate its configuration, or touch the database on
every parent interaction. Its address is carried forward from the owner's
previous token, and the child's own state advances only when the child itself is
addressed. This is what keeps composition cheap and keeps "compute together, own
together" a statement about deliberate sharing rather than an apology for
accidental work.

Two cases genuinely require the factory and pay for it:

- **A nullable slot.** Whether the slot is now absent is only knowable by asking,
  so a nullable child-producing property is evaluated on every owner interaction.
  Declaring a slot nullable is therefore a real cost, not only a schema flag, and
  the documentation should say so. A non-nullable slot is never evaluated to
  discover it still exists.
- **A keyed collection whose key set is recomputed.** Membership is derived from
  the owner's authoritative source, so the key set is computed on every owner
  interaction; children are then constructed only for keys absent from the live
  set, and live keys that disappear are removals.

Removal is decidable without construction in every other case: a fixed
non-nullable slot is never removed while its owner lives, and a keyed collection's
removals fall out of the key-set comparison. The owner never has to build a child
in order to discover it should be disposed.

For each received envelope, the client applies one staged operation:

1. separate entries carrying `error` from the rest, and set them aside; they
   advance nothing and take no part in the steps below;
2. decode every policy payload that is present, and reject duplicate or
   mismatched outer and signed addresses;
3. require every referenced child to be already live or introduced in the
   same `objects` collection;
4. create registry shells for all newly introduced addresses, reusing an
   existing registration when a referenced address is already live under the
   same owner;
5. reconcile each included object's signed snapshot, replacement schema, and
   `computed_data` into its stable proxy, **using the newest value the client
   holds for any half the entry omitted**;
6. bind canonical child paths to the resolved proxies and mark displaced
   children;
7. resolve callable-result address references, recording the producing address
   as each transient result's lifecycle owner;
8. morph component HTML;
9. dispose displaced children and explicit disposal effects, recursively
   following lifecycle ownership; and
10. deliver remaining effects and declared events from their source objects,
    then reject the pending operations of every entry set aside in step 1.

The same path with the same address preserves the existing proxy, editable
draft, Alpine scope, and request queue. A different address at that path is a
replacement; an absent nullable path is a removal. A newly referenced address
is introduced before the path becomes observable. These rules prevent an
owner refresh from clobbering a child's newer canonical or ephemeral state
while still making the owner's successor relationship map authoritative.

A named child's address is derived from its owner address, canonical attribute
path, configured Glue family, and declared key where the relationship is
keyed. The encoded address remains opaque to application code. A
server-authored parameter transition inside the child—such as a saved form
advancing `target_pk` from `null` to `42`—does not change that address. Callable
results instead receive fresh opaque transient keys, so repeated calls
introduce distinct children unless a dedicated addressed collection or named
property supplies stable identity.

#### Reintroducing an expired child

Owner and child tokens are re-signed only when their own address participates in
an interaction, so their lifetimes diverge. An owner refreshed on a timer keeps a
fresh token indefinitely while its untouched child form expires. Because the
owner's `children` map still names that child as live, the rules above would
never reintroduce it, and the page would be stuck until reload.

The request entry therefore carries an optional client-supplied
`reintroduce` list of canonical child paths:

```json
{
  "objects": [
    {
      "address": "dash#7f3a9c21",
      "policy_token": "...",
      "reintroduce": ["entry_form"]
    }
  ]
}
```

It is ordinary untrusted input and needs no signing, because the only thing it
can cause is that the server runs a slot factory it already declared and
authorizes the result from scratch. It cannot name an undeclared path, cannot
choose a family, cannot supply parameters, and cannot widen a capability. A path
that is not a declared slot fails admission.

The reintroduced child's address is unchanged — it is derived from the owner
address, canonical attribute path, family and key, none of which the expiry touched
— so the existing rule that *the same path with the same address preserves the
existing proxy, editable draft, Alpine scope, and request queue* applies. The
client keeps the user's work and receives a fresh token for it.

The reintroduced object is a new introduction on the server: its retained
state comes from the factory and, for a component, from `mount()`, never from
the expired token. Retained state the client cannot edit therefore restarts,
and the client's editable draft reaches the fresh object as ordinary `updates`
on its next call. Reading state out of the expired token would honor it past
its fixed lifetime (ADR 013); `component-system.md` §4 "Mount" records the
comparison with Livewire's equivalent boundary.

Client-side, an address whose entry returned `policy_expired` is marked stale
rather than disposed. Its proxy rejects further calls with a recoverable error
and names its owner, so composition code (or a default client behaviour) can
issue the owner request that repairs it. A page root has no owner and therefore
no reintroduction path; an expired root is a reload, which is the correct
outcome for a page whose session-scoped capability has run out.

A fixed named child may omit a key, in which case the property path itself is
its stable identity. If reevaluation may intentionally select a different
child for the same public path, the construction must supply a key derived from
that selection. Changing construction parameters without changing the key does
not rewrite an already-live child's signed parameters; the relationship either
preserves its address or explicitly replaces it through a new key.

The client attaches a local generation to each live address registration and
accepts a response entry only for the generation that issued its request. That
generation is neither policy state nor a server security control; it prevents
late responses from a disposed client incarnation from patching a newly
introduced object at the same address. Client disposal does not invalidate a
signed token on the server.

#### Callable capability and server injection

Callable capability is positive and per callable. Each callable in the signed
policy names the arguments that this token permits the client to supply; the
unsigned static data describes their types, defaults, and presentation:

```json
{
  "capability": {
    "callables": {
      "save": { "allowed_arguments": ["force"] }
    }
  },
  "static_data": {
    "callables": {
      "save": {
        "parameters": {
          "force": { "type": "boolean", "required": false, "default": false }
        }
      }
    }
  }
}
```

The effective client-input set is the intersection of the signed
`allowed_arguments` and the current callable declaration. Static data is not an
authority source. Consequently, adding a new callable argument does not grant
it to previously issued tokens.

Server-injected parameters are classified from the current callable's
annotations through a closed injection registry; `HttpRequest` is the first
built-in injected type. Injected parameters are omitted from both
`allowed_arguments` and client static data. If a request nevertheless supplies an
argument currently classified as injected, Glue rejects the entire request
during protocol admission, before invoking the callable, and issues no
successor token. This current-declaration check also protects an old token if a
formerly client-supplied parameter later becomes injected.

**The registry reserves names as well as types.** Classifying on annotations
alone leaves the most likely mistake open: an unannotated `def save(self, request)`
would classify `request` as ordinary client input and accept a forged value,
which is the verified `comparative-analysis` §4.3 finding surviving in the form
a developer is most likely to write by accident. Each registry entry therefore
declares both a type and a reserved parameter name. A parameter matching a
reserved name is injected regardless of annotation; a parameter matching a
reserved name whose annotation contradicts the registry is a declaration error
raised at schema compilation, not a runtime coercion. A developer who genuinely
wants a client-supplied value must not name it `request`.

Ordinary annotations such as `bool` describe client input and do not reserve a
name.

A callable accepting `**kwargs` does not imply an open client-input capability.
Its permitted extra names must be declared explicitly and included in the
signed `allowed_arguments`; otherwise they are rejected. Variadic forwarding
must never reintroduce a server-injected argument.

The encoding may embed this envelope directly in the token, as the current
policy does with identity, or bind a separately serialized envelope by
signature. The invariant is the same: the signature covers the exact values;
merely placing unsigned state beside a valid policy token does not authenticate
that state. Signing provides integrity, not confidentiality, so the envelope
must not contain secrets merely because it is opaque to normal client code.

#### Integrity, replay, and concurrency contract

A policy token proves that Glue issued the exact capability and values and that
the token is within its configured lifetime. It is not universally
single-use and does not, by itself, prove that it is the newest token ever
issued for the address. An older unexpired token may be replayed under the
default stateless contract.

That boundary has five consequences:

1. Session, user, address, capability, and current application authorization
   are checked on every call. Signed retained state never substitutes for
   reauthorization.
2. The browser serializes calls for one canonical address: the next call is not
   sent until the prior response has advanced canonical data and the token.
   Independent addresses may proceed concurrently.
3. An adapter whose correctness requires freshness may declare an authoritative
   version. Glue signs the observed version and compares it with current
   server-side data before applying updates or invoking the action. A mismatch
   returns a stale-state response and authoritative refresh rather than running
   the call.
4. Database mutations still use transactions, row locking or optimistic
   concurrency as their domain requires. Non-idempotent external side effects
   still require a domain idempotency key; the policy token is not one.
5. Separate tabs may branch token-only state. Preventing that requires an
   authoritative shared version or server-held latest-token state and is opt-in,
   not a hidden cost imposed on every Glue object.

A counter or nonce carried only inside the signed token does not prevent replay:
an older counter remains validly signed. General one-time semantics require the
server to remember the latest nonce in a session, cache, or database. Glue keeps
stateless replayable tokens as the default and uses authoritative version checks
where stale execution matters.

#### Authenticated queryset continuation

`QuerySetGlue` continues to accept an arbitrary server-authored Django queryset
from a view. Preserving both that ergonomic contract and stateless reconstruction
requires the queryset's opaque Django `Query` representation to remain in the
signed policy token; Glue does not invent a partial ORM serialization protocol or
require every queryset to become a registered provider.

The query pickle is authenticated continuation data, never client input. Glue
must enforce token-size and encoded-query-size limits, verify the signature,
subject, session, expiry, namespace, and signed expected-model identifier before
deserialization, and only then decode and unpickle through one narrow path. The
resulting query's model must immediately match that signed identifier before the
query is used. No update, callable argument, static data value, `computed_data`, or
other unsigned request value may reach that path. The reconstructed base
queryset still bounds every client query and the signed query capability still
governs all client-added filtering and ordering.

That narrow path uses an **allowlisting unpickler**: a `pickle.Unpickler`
subclass whose `find_class` admits only the ORM, expression, field and standard
value types a serialized `Query` can legitimately contain, and raises on
anything else. This is defence in depth behind the signature, not a replacement
for it — the signature is what makes the payload trustworthy, and the allowlist
is what limits the damage when the signature is not. Livewire added its
`SecurityPolicy` class deny-list *behind* an already-verified checksum after a
published gadget-chain disclosure; the same reasoning applies here, and an
allowlist is the stronger form of it. The allowlist is a published, versioned
part of the contract so that a project with custom lookups or expressions can
extend it deliberately rather than discovering an opaque failure.

The same path carries choice-source continuations, so `choices=` sources decode
through the identical unpickler and size bounds rather than a second
deserialization route.

This accepts that disclosure of the signing `SECRET_KEY` permits policy forgery
and makes queryset deserialization part of the already-severe application secret
compromise. Signing provides integrity but not confidentiality: query structure
and embedded constants are visible to the browser and must not contain secrets.
An optional server-backed continuation store may be added for deployments that
prefer stateful storage, but it cannot change the public `Glue.queryset(queryset)`
contract.

Editable updates have two distinct validation stages:

1. **Protocol admission** checks the current declaration and signed capability,
   current authorization, path, allowed callable arguments, server-injected
   argument collisions and reserved names, payload shape, decoding, and resource
   limits. An unknown, non-editable, unauthorized, malformed, or structurally
   unsafe update or argument fails the request before the action runs. Glue does
   not issue a partially advanced successor token.

   Admission covers **argument interiors, not only argument names.** An
   allowlist over names is insufficient wherever a single admitted argument is a
   mapping keyed by field names, because the exposure decision then lives inside
   the value. Any declared argument whose type is a field-keyed mapping must
   name the projection it is keyed by, and admission validates every key against
   that projection before the callable runs:

   - `QuerySetGlue.new(initial)` requires signed `ADD` access and is keyed by the
     queryset's **editable** projection. An unexposed or non-editable key fails
     admission. Without this rule `new()` is unconstrained mass assignment over
     the whole model, including fields deliberately excluded from `fields` — the
     same class of defect as an unchecked filter path, through a different door.
   - `QuerySetGlue` filter and ordering controls are keyed by the signed query
     capability (§4).
   - `FormSetGlue` keyed form updates are keyed by stable membership keys and
     each form's own editable projection.

   A declared argument that is an unkeyed structure — Editor.js blocks, a
   proposed order list — is bounded and validated by its declared serializer
   instead, and is never interpreted as a field projection.
2. **Domain validation** checks whether an admitted draft can be used by the
   requested action: Django field and form validation, `Model.full_clean()`,
   uniqueness, cross-field rules, and application invariants. Failure does not
   reject the draft. The successor token acknowledges it in `state_snapshot`,
   while `computed_data` carries the recomputed errors.

This follows Livewire's handling of ordinary validation failures and preserves
Django's bound-form semantics. A submitted invalid value remains visible even
when the user has made no newer edit since sending the request, because it is
the successor canonical draft rather than a special rejected client value.
Signing that draft proves continuity only; every action must validate and
authorize it before domain use. When a save succeeds, the adapter clears its
errors and may rebase the successor snapshot to normalized or persisted server
values.

A failed `FormGlue.save()` therefore has this conceptual result:

```json
{
  "decoded_policy_token": {
    "target": {
      "parameters": { "target_pk": 42 }
    },
    "state_snapshot": {
      "email": "not-an-email",
      "display_name": "Chase"
    }
  },
  "computed_data": {
    "fields": {
      "email": {
        "errors": ["Enter a valid email address."]
      }
    }
  }
}
```

The form draft is now the baseline for the next request, but the instance with
PK 42 remains unchanged. A successful later save may normalize the email and
rebase `state_snapshot`; a successful create may additionally advance
`target.parameters.target_pk` from `null` to the new PK.

`static_data` describes the client-visible interface needed to construct field
and attribute projections: types, labels, widgets, callable shapes, and
state-path mappings. It normally ships when an address is first introduced.
If that interface later changes, the server may send a replacement
`static_data` atomically with the successor token and `computed_data`;
unchanged `static_data` is omitted. The
client applies a replacement without changing the addressed proxy's identity.

Static data describes shape, not authority. It never grants access, and the server
must not consult a browser-returned copy. Effective permission still comes from
the current server declaration, signed capability, and current application
authorization. Static data therefore never returns to the server.

Response `computed_data` is the complete current down-only output for that
address, not a diff. Like `static_data`, it is not covered by the
policy-token signature, is never returned to the server, and must never be
used for server reconstruction or hydration. It is still authoritative when
received as part of the server response. Both downward channels are unsigned
in that signature sense, and neither is an invitation to accept such values
from a request.

The two downward channels are keyed by volatility, not by that shared
boundary: `static_data` is a function of the declaration and access — stable
for the token's lifetime, resent only when the interface itself changes —
while `computed_data` is a function of current state, re-derived as the
request touches it.

The client derives the actual response patch using the reconciliation in §5. A
response affecting several objects contains one policy-token/`computed_data`
pair per canonical address. Requests follow the same rule: the normal case
contains one addressed object entry, while independent refreshes, targeted
invalidation, or interactions spanning established Glue families may batch
only the independently addressed entries that participate. A batch never embeds
one policy token inside another, supplies ancestor authority, or merges state
snapshots. Every entry is reconstructed, admitted, authorized, advanced, and
reconciled against its own address. `effects` and fragments never mix into
`computed_data`. Batching provides no causal ordering: a parent refresh that
must observe a child save is a subsequent request, normally triggered after
the child's result or declared event. A truly atomic cross-object transition
belongs to one authorized callable.

A configured Glue object returned by a typed `@Glue.property` on any addressed
Glue object is a named addressed child, not a value inserted into the parent's
state snapshot. The parent's signed `children` map carries the child address; the
child carries its own policy, retained state, editable drafts, and response
entry. The relationship does not make child state available during an isolated
parent reconstruction and does not cause automatic parent refresh. Client code binds directly to the
reactive child where possible and explicitly sequences a parent refresh or
callable after a child outcome when parent-owned output must change.

When a callable directly returns a declared configured Glue object, its newly
introduced per-address entry is included with the caller's response. The
caller's wire `result` is that address; the callable schema marks the return as
a Glue-object reference, so an ordinary string result is never ambiguous. The
client registers all object entries before resolving the public result, so
application code receives the reactive proxy rather than a manifest or serialized
Django object. The introduced capability cannot exceed the caller's effective
capability and is still intersected with the returned object's configuration and
current application authorization.

**A transient callable result is not recorded in the owner's signed `children`
map.** That map carries declared property children and keyed collection items
only — both bounded by declaration. A transient result has no stable public path
to bind, its key is opaque and freshly minted per call, and recording it would
make the owner's token grow without bound across a session while leaving a signed
reference that the client can legitimately tear down on its own.

Its lifecycle ownership is **client registry bookkeeping**, in the same category
as the DOM-node associations that §Shared derivation already keeps out of the
policy. The client records the producing address when it registers the introduced
entry, and that record is what drives recursive disposal.

Every behaviour the signed record would have provided is preserved elsewhere:

| Required behaviour                   | Where it now comes from                                                                                                       |
| ------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------- |
| Address derived beneath the caller   | The address is minted from the owner address and an opaque transient key at issuance, and is carried in the child's own token |
| Capability capped by the caller's    | Enforced at issuance, baked into the child's signed policy, and re-intersected with current authorization on every request    |
| Result resolves to a live proxy      | The child is an ordinary entry in the same`objects` collection, registered before `result` is resolved                    |
| Owner disposal cascades to it        | The client registry's recorded producer, which is also what cancels its queued calls and rejects late responses               |
| One lifecycle owner per address      | Unchanged; the client registry enforces it, and an address introduced under two owners is still an error                      |
| Server can authoritatively remove it | `effects.dispose`, which already exists precisely for "a nonvisual object is authoritatively removed"                       |

One mechanism is genuinely given up: an owner can no longer revoke a transient
child by omitting it from a successor `children` map, because it was never in
one. `effects.dispose` is the replacement and is strictly more explicit — a
server that means to tear down a transient result says so, rather than expressing
it as an absence.

Two defects close as a consequence. The owner's token no longer grows with call
count, and a client that disposes a transient result when its modal closes no
longer leaves a signed reference behind — so the staged-apply requirement that
every referenced child be live or introduced has nothing stale to reject.

#### Responses omit what did not change

An addressed response carries a successor token and complete `computed_data`
*when either changed*. Both are omitted when they did not, and both omissions are
**derived rather than declared** — there is no flag, because `updates_client_state`
was exactly such a flag and it conflated direction with timing.

**Token omission.** After the interaction, Glue compares the object's retained
values — parameterized values, non-parameterized state, and the `children` map —
against the values the verified incoming token carried. Values that are opaque
or expensive to serialize, notably a queryset's authenticated continuation,
are compared by object identity: if the adapter still holds the object it was
reconstructed with, the input is unchanged by construction. When nothing
changed, the incoming token remains exactly valid and is not reissued. The entry
simply omits `policy_token` and the client keeps the token it has.

**`computed_data` omission.** An adapter that did not re-derive its downward
output omits the key entirely. When present it remains complete rather than
differential; "omitted" and "empty" are therefore distinct, and the client
treats omission as *unchanged* and an empty object as *everything removed*.

This matters because it is the difference between a workable and an unusable
read path. Search-as-you-type against a `QuerySetGlue` calls a read-only attribute
per keystroke. Unconditional reissue would pickle the query, base64 it, and sign
it on every keystroke, and unconditional `computed_data` would re-run the query to
resend rows the caller did not ask for. The current code avoids both with
`updates_client_state=False` on `foreign_key_choices`, `query_with_params`,
`count`, `get`, and `new` — that flag is deleted, and these rules are what replace
the behaviour it was protecting.

One consequence to accept knowingly: a token that is not reissued does not have
its expiry extended, so a session spent entirely on read-only calls will
eventually reach expiry and recover through the reintroduction path rather than
rolling forward indefinitely. That is the correct reading of a capability
lifetime — activity on an object is not the same as re-authorization of it — but
it must be weighed when the policy lifetime is finally chosen.

#### Policy-token size and transport bounds

Policy size is controlled first by ownership, not encoding. Each addressed
object carries one complete, self-contained token containing only the
parameterized values, reconstruction configuration, capability,
non-parameterized reconstructors, acknowledged editable drafts, and shallow
child bindings that the server needs on its next request.
Parent and child tokens never contain one another, and selective batching never
submits the mounted tree implicitly. An owner token contains only its shallow
path/address `children` map, never child policy or state. Static data, derived
output, and database-derived row data remain outside the token. Collection
keys enter `state_snapshot` only under the consumption rule in §8; current
owned-child bindings still appear in `children` so the next successor can
authoritatively preserve, replace, or remove the corresponding client proxies.

This makes growth linear in genuinely retained data, but does not promise that
arbitrarily large client-held state is cheap. A large document, unbounded edit
buffer, or database-derived collection should remain widget state, be stored
durably, be submitted as validated callable input, or be split across genuine
ownership boundaries. Compression cannot repair an incorrect ownership model.

An illustrative probe against Glue's current uncompressed Django signer
produced a 759-byte small-component token, a 1.85-KiB token for twenty short
form fields, a 3.24-KiB token for one hundred ordered keys, a 26-KiB token for
one thousand ordered keys, and a 4.36-KiB token carrying a two-KiB opaque query
value. These synthetic numbers establish scale only; production-shaped forms,
formsets, queries, and batches determine the defaults.

The transport requires configurable bounds at five layers:

1. encoded policy-token bytes before decoding;
2. decoded policy-envelope bytes;
3. encoded queryset-continuation bytes before base64 decoding or unpickling;
4. addressed-object count and aggregate bytes in one batch;
5. introduced-object count and aggregate token bytes in one page render.

The fifth bound exists because collections are where aggregate weight actually
lands. A `QuerySetGlue` or `FormSetGlue` introduces one independently signed
child per row, so the page — not the request — is the payload that grows: a
hundred rows at the probe's 759-byte small-object scale is roughly 75 KiB of
tokens before any state, and a hundred twenty-field forms is closer to 185 KiB.
Per-object bounds cannot see this, because no individual object is large. A
render that exceeds the bound fails loudly and names the introducing object, so
the remedy is a smaller page or a narrower projection rather than a silently
heavy document.

Exceeding a bound fails loudly before application dispatch. Glue never
truncates state, silently drops batch entries, or automatically changes an inline
token into server-held state. A server-backed continuation backend remains a
future explicit deployment choice for applications that accept its persistence
and eviction semantics.

The physical token encoding is internal and versioned. Token-level compression
is not part of the semantic contract: HTTP compression already reduces normal
downward responses, while inline compression primarily benefits request bodies
and browser storage and would require a bounded client decoder. Implementation
benchmarks must choose concrete default limits and determine whether adaptive
compression earns that complexity. Encoded and decoded bounds still apply if
compression is introduced.

---

## Consequences

- **Breaking for every consuming project.** `identity=True`,
  `takes_client_state`, `updates_client_state` and `loading_strategy` all change.
  Measured migration cost, counting **consuming projects only** (stratusadv-portal
  plus django-spire — library-internal occurrences are changed by the refactor
  itself and migrate nobody):

  | Flag                     | Sites to migrate | Library-internal |
  | ------------------------ | ---------------- | ---------------- |
  | `takes_client_state`   | 22               | 26               |
  | `updates_client_state` | 13               | 20               |
  | `loading_strategy`     | 4                | 57               |
  | `identity=True`        | 2                | 5                |

  `loading_strategy` looks alarming in the codebase and is almost entirely
  internal: 4 consumer sites against 57 in the library and its tests.
- **The wrong default disappears rather than being renamed.**
  `updates_client_state=False` appears 8 times inside the library and in 3 of 5
  portal `html_attr` uses. Authoritative response reconciliation removes its
  *correctness* motive, and the derived omission rules in §10 remove its
  *performance* motive — the flag's real job at `foreign_key_choices` and the
  queryset read attributes was avoiding a re-pickle and re-sign per keystroke, and
  deriving the omission does that without a declaration.
- **`docs/future/attribute-glue-unification.md` is superseded in detail.** Its
  goal of one state and transport pipeline is adopted, but attributes do not
  become `BaseGlue` subclasses. `BaseGlueAttribute` and
  `GlueObjectAttribute` disappear in favor of lightweight attribute definitions
  and independently addressed children (§4).
- **These are removed** (audit rulings): `LoadingStrategy.INHERIT` (one
  occurrence — its own definition), `TemplateGlue` and `initial_context_data`
  (no callers in either project; removal also eliminates client context
  shadowing), `Glue.sequence()` as an entrypoint, the three-event listener
  system (zero consumers; deprecate first, it is published API), the portal's
  four dead `Glue.function` registrations. The replacement semantic-event
  contract is not a preservation of those hooks: it carries declared server
  output, not client transport observations named `before`, `after`, and
  `error`.
- **`loading_strategy` is removed, not renamed.** `LoadingStrategy`, the
  per-object `loading_strategy` option, the page-load entry's
  `loading_strategy` field, the `load_state` callable, and the client's
  first-access lazy fetch all go (ADR 002). Every introduced entry is a complete
  first snapshot (§10 "Page load"); on-demand re-derivation is `$refresh()`.
- **`Glue.function` stays.** It is live in spire's chart contrib via
  `window.Glue?.function?.[this._glue_name]`, driving five chart classes.
  Replacing it with `Glue.attr` on an object is a migration, not a deletion.
- **`related_field_config` is removed.** Relationship projection folds into
  ordinary `fields`/`exclude` paths with optional `Glue.fields()` sugar, and
  relationship choice sources move to a separate `choices` mapping. The one
  production caller migrates mechanically. Related-object defaults close, and
  ORM loading directives no longer alter exposure.
- **Write exposure becomes its own projection.** `editable=` narrows the derived
  `field.editable` set on models and forms. Existing declarations are unaffected
  because the omitted default reproduces current behaviour, but a project editing
  sensitive rows should supply it deliberately (§9).
- **Creation becomes its own access level.** `GlueAccess.ADD` extends the cascade
  to `VIEW < ADD < CHANGE < DELETE`, enabling create-only querysets and relation
  collections without an `allow_create` flag. Persisted rows from an ADD-only
  collection remain `VIEW`; ADR 009 and §4 define the draft transition.
- **`authorize()` is new public API on every `BaseGlue`.** Its default is
  permissive, so nothing breaks on adoption; it is the named seam for the
  object-level permission rule that invariant 4 requires and that no amount of
  signing can supply (§3).
- **Responses gain a per-address `error` channel.** Address-scoped faults —
  expiry, authorization denial, admission failure — no longer fail a whole batch
  (§10). `GlueResponse.from_error`'s whole-response shape survives for envelope
  faults only.
- **`$refresh()` no longer submits editable drafts by default.** Polling a form
  therefore stops pushing half-typed input, and `$refresh({submit: true})` is the
  explicit form (§6).
- **Server injection reserves names as well as types.** An unannotated parameter
  named `request` becomes a declaration error rather than a client-writable
  argument, closing the remaining half of `comparative-analysis` §4.3.
- **`Glue.view` is promoted and moved onto normal HTTP dispatch.** Sixteen sites
  make it the second-heaviest entrypoint and the de facto component mechanism.
  Direct requests to the target URL plus response-only content negotiation
  close the middleware bypass in `research/comparative-analysis.md` §4.6 without adding
  view registration ceremony.
- **Operational security hardening does not block the state model.** Policy
  lifetime cleanup, general request limits, invalid-token throttling, anonymous
  session churn, session-rotation recovery, and CSP support are tracked in
  `roadmap.md`. Narrow size checks that protect queryset
  deserialization remain part of the authenticated-continuation contract and
  are not deferred.

Implementation order, gates, and deferred work are maintained in
[`roadmap.md`](../../roadmap.md).

---

## Rejected Alternatives

- **Annotation-driven declaration** (`date: datetime.date` alone makes it
  state). Too implicit; the declaration must be explicit. Annotations are read
  for coercion only.
- **A separate `Glue.state()` descriptor.** The value roles are genuinely
  disjoint and the implementation would simplify, but `Glue.attr` is established
  and familiar to the team. The split happens internally instead, invisible to
  call sites.
- **`locked=True` as the name for signed round-tripping.** Locking is already
  the reconstructor default, and under-describes the role: Livewire's
  `#[Locked]` means only "client cannot write," not whether a value is exposed
  as a construction parameter.
- **`signed=True` as the public name.** Exposes mechanism rather than guarantee.
  The role names what the value is; signing is the consequence.
- **A `direction=` parameter taking `SIGNED | DOWN | BOTH | LOCAL`.** Drafted and
  rejected: it leaks the maintainer's analytical frame into the public API, and
  the enum is not even coherent — `SIGNED` is a protection mechanism, `DOWN` and
  `BOTH` are directions, `LOCAL` is a location. Three kinds of answer in one
  enum. Roles name what a developer actually means; direction is derived.
- **"Frequency" for the second question.** None of its answers is a rate.
  Calling it frequency would also conflate value inclusion with client
  scheduling: periodic polling initiates an exchange, while Timing describes a
  value inside one.
- **Incremental cleanup alongside component work.** The defects are at
  `BaseGlue`; every component authored first becomes a migration, and the
  channels compose across the address tree.
- **Livewire's entire client-facing snapshot round-tripping upward.** Glue's
  signed token carries the narrower subset the server will consume:
  `target.parameters`, `state_snapshot`, and the shallow `children` map.
  Derived output and static data remain downward-only because Glue recomputes or
  ignores them.
- **Universal one-time tokens.** True replay prevention requires shared
  server-side latest-token state, complicates concurrent tabs, and removes the
  stateless property from every object whether it needs freshness or not.
  Authoritative version checks provide that guarantee where it matters.
- **A signed nonce or counter with no authoritative comparison.** It detects
  tampering but not replay because every previously issued value remains
  validly signed.
- **Provider-only queryset reconstruction.** It avoids client-held query
  pickles, but makes an arbitrary queryset constructed naturally in a Django
  view insufficient for `Glue.queryset()`. That loss of ergonomics is not
  accepted. A provider may remain an optional construction pattern, not a
  requirement.
- **Unicorn's `Meta.exclude` / `javascript_exclude`.** A weaker deny-list
  version of what glue already does; its two CVEs are the argument against
  drifting toward it.
