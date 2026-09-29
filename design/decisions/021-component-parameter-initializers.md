# ADR 021: Model and Dataclass Component Parameters

Status: Accepted; implemented on branch

Date: 2026-09-28

## Context

A component that represents a database row selects it through a scalar parameter
and loads the row itself, because parameters are validated against their
annotation and JSON-encoded into `target.parameters`:

```python
class TimeEntryFormModalComponent(Glue.Component):
    entry_id: int = Glue.ComponentParameter()

    @cached_property
    def entry(self):
        return TimeEntry.objects.active().get(pk=self.entry_id, user_id=self.user_id)
```

Two costs follow.

- **The row is loaded twice when a parent already has it.** The portal's
  `TimeEntryDayComponent.edit_entry_modal` loads the entry to check it, then
  constructs the modal with `entry_id=entry_id`, and the modal loads the same row
  again. A parent stamping row components from rows it has just loaded pays one
  query per child for data it already holds.
- **Every such component repeats the same boilerplate.** A key parameter, a
  `cached_property` that loads it, and the scope that lookup applies are spread
  across two declarations, and nothing in either says what the component actually
  represents.

A component instance does not survive between requests. The first render builds
it, runs `mount()`, and discards it; an action rebuilds it from its signed token,
and `mount()` does not run again. Only the signed token carries over, and it
carries JSON values, never a model instance. So a component has exactly two ways
to obtain its row: the instance a construction site supplies during the render
that builds it, or a lookup by key on every later request. The design below makes
both explicit in one declaration.

This record is justified by that duplication and boilerplate. It does not make
lists of per-row components a recommended pattern: a plain list stays one owning
component with rows as template partials, as `component-system.md` §4 describes.

Separately, a parameter annotated with a dataclass half works today. Construction
validates it, because the serializer registry coerces through pydantic's
`TypeAdapter`, and reconstruction would restore it the same way. But
`target.parameters` is encoded by the legacy `GlueResponseJSONEncoder`, which does
not know dataclasses, so the component fails with `TypeError: Object of type ...
is not JSON serializable` as soon as it renders. `state-model.md` §7 already
specifies a two-way registry that replaces that encoder; only its decode half is
implemented for parameters.

## Decision

**A component parameter may be declared by decorating a method with
`Glue.ComponentParameter`.** The method is the parameter's initializer: it turns
the parameter's primary key into the model instance the component works with.

```python
class TimeEntryFormModalComponent(Glue.Component):
    template = 'time_tracker/component/time_entry_form_modal.html'

    @Glue.ComponentParameter
    def entry(self, pk: int) -> TimeEntry:
        return TimeEntry.objects.active().select_related('project').get(pk=pk, user_id=self.request.user.pk)
```

```python
@Glue.attr(required_access=Glue.Access.CHANGE)
def edit_entry_modal(self, request: HttpRequest, entry_id: int) -> TimeEntryFormModalComponent:
    entry = TimeEntry.objects.active().select_related('project').get(pk=entry_id, user_id=self.user_id)
    return TimeEntryFormModalComponent(entry=entry, access=self.access)
```

`Glue.ComponentParameter` therefore has two forms: the value form declares a
scalar parameter, and the decorator form declares a model parameter with its
initializer. Both declare the same thing, a signed construction input that defines
what the component is.

**Declaration rules.**

- The method name is the parameter name. `self.entry` reads the resolved instance;
  construction sites pass `entry=`.
- The method takes one argument, the primary key, and its return annotation must
  be a Django model class. Any other signature or return annotation raises
  `GlueComponentParameterError` at class definition.
- An initializer is never a client-callable attribute. It does not appear in the
  capability's callables, and the client cannot invoke it.
- The decorator form does not accept `editable=True`. Changing which row a
  component represents is done by server code, as described below.

**The signed token carries the key, never the row.** `target.parameters` holds the
instance's primary key. The model comes from the declaration, not from the token,
so a token cannot redirect a parameter to another model.

**Construction accepts the instance or its key.**

- An instance of the declared model is used as supplied, without calling the
  initializer. `is_authorized()` still runs at introduction.
- A primary key is passed to the initializer. That covers `as_view()` URL
  captures and construction sites that only have a key.
- Any other value raises `GlueComponentParameterError`.

**Reconstruction passes the signed key to the initializer.** Every later request
calls the initializer with the signed key, the live request bound, and the
component's other parameters assigned, so the scope the initializer applies is
re-applied on every interaction: a row that has left the user's scope stops
resolving on the next interaction, not when the token expires. If the initializer
raises the model's `DoesNotExist`, the address fails with the existing
`model_instance_not_found` error and receives no successor token. Other exceptions
propagate as they would from any reconstruction step.

**Resolution is lazy and happens at most once per object.** Glue binds the
request after it reconstructs an object from its token, so the initializer runs on
the first read of the parameter, not inside the constructor. By then the request
is bound and every scalar parameter is assigned. An initializer may read another
model parameter; a cycle between them raises `GlueComponentParameterError`. The
result is kept for the life of that object.

**Server code may assign to a model parameter.** An action retargets its component
by assigning an instance or a key:

```python
@Glue.attr
def show_next_entry(self) -> None:
    self.entry = self.entry.next_in_period()
```

The assigned value follows the construction rules: an instance is used as
assigned, and a key is resolved through the initializer on the next read. The
signed key changes, so the component re-renders, as it does for any parameter
change.

**The initializer is a value provider, not a lifecycle hook.** It returns the
instance for one key. It must not assign to `self`, write to the database, or
otherwise change state, and Glue decides when it runs. That is the distinction §4
already draws for `is_authorized()`: the rejected `hydrate()`, `dehydrate()`, and
`boot()` hooks let application code act inside signed reconstruction, while an
initializer answers one question at a fixed point in it.

**A supplied instance must match what the initializer returns.** The component is
written against one shape of its row: the related selections and annotations its
initializer loads. An instance resolved on a later request always has that shape,
so an instance supplied at construction or by assignment must have it too. The
code supplying it is responsible for loading it the same way.

**Glue verifies that contract in development.** The setting
`DJANGO_GLUE_VERIFY_MODEL_PARAMETERS` defaults to Django's `DEBUG`. When it is on,
the first read of a supplied instance also calls the initializer with its key,
once the request is bound, and:

- raises `GlueComponentParameterError` if the initializer raises `DoesNotExist`,
  because the supplied row is outside the component's scope; and
- emits `GlueModelParameterMismatchWarning`, naming each annotation or loaded
  relation the resolved instance has and the supplied one lacks, and uses the
  resolved instance in its place.

Verification costs one initializer call per supplied instance, which is why it is a
development check. With verification off, a supplied instance is trusted, as every
other server-supplied construction input is. `GlueModelParameterMismatchWarning` is
a public warning class, so a project can escalate it to an error in its test suite.

**The key conversion is a built-in serializer handler.** It encodes a model
instance to its primary key for `target.parameters` and decodes the signed key to
the primary key's Python type before the initializer receives it. It never loads a
row; the initializer does. A model instance is not a `BaseGlue` object, so the
hard composition boundary is unchanged: only the key enters `target.parameters`,
and a model instance never appears in `state_snapshot`, `computed_data`, updates,
or event detail.

**Dataclass parameters are encoded through the serializer registry.** A value
parameter annotated with a dataclass is signed as its JSON form and restored as an
instance of that dataclass:

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class ReportWindow:
    start: datetime.date
    end: datetime.date
    budget: Decimal


class BudgetPanelComponent(Glue.Component):
    window: ReportWindow = Glue.ComponentParameter()
```

- Encoding uses the same `TypeAdapter` as decoding, in JSON mode, so the two
  directions are symmetric by construction: nested `date`, `Decimal`, and enum
  fields are written as JSON and restored as their Python types.
- The rule applies to every value parameter, not only dataclasses: a parameter is
  encoded through its annotation's adapter, which completes §7's two-way registry
  for `target.parameters` and retires `GlueResponseJSONEncoder` there.
- A dataclass parameter follows the ordinary value-parameter rules. Like any
  parameter it is fixed once stamped unless declared editable, and a field holding
  a model instance or a Glue object is rejected, because neither has a JSON form;
  a row belongs in a model parameter.

**Forms are built from model parameters, not passed as parameters.** A component
that edits its row exposes the form as a child built from the parameter:

```python
@Glue.property
def entry_form(self) -> FormGlue:
    return Glue.form(target=TimeEntryForm(instance=self.entry))
```

**Other parameter types are out of scope.** Querysets, form classes, form
instances, and values derived from other parameters were considered and are
recorded in `concerns.md` with the reasons and the conditions for reopening them.

**Specification changes.** `component-system.md` §4 names the handoff and the
partial-first guidance in its shared-derivation paragraph, its identifier
paragraph names the model form, and "Hydration is framework-owned" records the
initializer as a permitted value provider. `state-model.md` §1 records the
construction, reconstruction, assignment, and verification rules for model
parameters, and §7 lists the model-key handler among the built-in serializers and
states that parameters are encoded through their annotation's adapter.

## Consequences

- A construction site that already holds the row supplies it, and the component
  issues no query for it. The portal's modal factories stop loading each entry
  twice. A component built from a key, or rebuilt for an action, costs one
  initializer call, as its `cached_property` lookup costs today. Model parameters
  are never slower than the key-plus-`cached_property` pattern they replace.
- What a component represents, its scope, and its shape are declared in one method.
  The key parameter and its loading property collapse into one declaration.
- Scope is re-applied on every interaction, and `is_authorized()` stays a predicate
  about operations.
- A construction site that supplies an instance of the wrong shape or scope is
  caught in development. In production it is trusted, so a mismatch there behaves
  differently on the first render than after an action. Projects that want the
  guarantee in CI escalate `GlueModelParameterMismatchWarning` to an error in tests.
- Existing scalar parameters keep working. Migrating a component replaces its key
  parameter and loading property with one initializer, and its construction sites
  may keep passing keys.
- The client is unaffected. Tokens are opaque to it and carry only the key.
- Dataclass parameters work instead of failing at render, and structured
  parameters no longer need to be flattened into several scalars or a loosely
  typed `dict`. Encoding every parameter through its adapter removes the legacy
  encoder from the parameter path, so a type the adapter accepts on the way in is
  one it can write on the way out.
- `Glue.ComponentParameter` gains a decorator form. `concerns.md` already records
  that `Glue.attr` decorating a method means a client-callable attribute; using
  `Glue.ComponentParameter`, not `Glue.attr`, for initializers keeps the two
  readings distinct.

## Rejected Alternatives

- **Loading the row in `mount()`.** `mount()` runs only on the first render, so the
  row is missing on every action. Loading it in both places is the
  `cached_property` pattern this record replaces.
- **A `queryset=` option on the parameter, as a queryset or a callable of the
  request.** A static queryset cannot express a scope that depends on the user or
  tenant. A callable handles that but is limited to one expression over the
  request, cannot use the component's other parameters, and adds a second
  declaration beside the parameter.
- **A queryset hook bound to the parameter (`@entry.queryset`).** It splits one
  parameter across a value declaration and a method. The initializer is the method.
- **A `get_queryset(self, parameter)` method.** It dispatches on a parameter name
  string and grows a branch per parameter.
- **Scoping rows in `is_authorized()`.** Row visibility is a data question for the
  query, not an operation permission, and filtering after loading is the wrong
  layer.
- **Trusting the signed key without re-applying scope, as `ModelGlue` does.** A row
  that left the user's scope would stay actionable until its token expired. The
  initializer re-applies scope at no extra cost, since reconstruction must load the
  row anyway.
- **An editable model parameter.** The client could propose a key that the
  initializer resolves, but editable values arrive as drafts, and resolving a
  draft key lazily would fail wherever it is first read rather than where the
  update is admitted. Retargeting by server assignment covers the need without
  that timing question. It can be reconsidered with admission-time resolution.
- **A request-scoped cache primed by the parent.** The coupling is a string-key
  convention outside both classes, and a value cached before a write in the same
  request is stale after it. This is the cross-object cache §4 prohibits.
- **An unsigned preload argument on `{% glue_component %}`.** A separate
  `preload=` value used only for the first render would give one input two
  meanings and two code paths.
- **Decoding through the model's default manager.** A signed key would then
  resolve any row of the model, including soft-deleted rows and rows outside the
  consumer's scope.
- **Always verifying a supplied instance.** It would add one query per supplied
  instance in production, the cost this record removes.
