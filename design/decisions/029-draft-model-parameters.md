# ADR 029: Draft Model Parameters

Status: Accepted; implemented on branch

Date: 2026-10-06

## Context

[ADR 021](021-component-parameter-initializers.md) declares a model parameter by
decorating an initializer that turns a primary key into the row the component works
with. The parameter must name a saved row: `None` and an unsaved instance both raise
`GlueComponentParameterError`.

That leaves out the most common reason to build a form component, which is to create
a record or edit one with the same component. Such a component cannot use a model
parameter today. It falls back to the pattern ADR 021 set out to remove: a nullable
scalar key, and a method that returns a blank instance or loads the row. django-spire's
`ModelFormComponent` is written this way.

A component instance does not survive between requests, and its token carries JSON
values, never a model instance. A row that does not exist yet has no key to sign. So
the only thing a token can say about it is that there is no key, and the only code
that can build it on every request is the initializer.

## Decision

**A model parameter whose initializer's key annotation admits `None` accepts a
draft.** The construction site leaves the parameter out, and the initializer is
called with `None` and returns the row to work with, usually an unsaved instance.

```python
class TimeEntryFormModalComponent(Glue.Component):
    template = 'time_tracker/component/time_entry_form_modal.html'

    day: date = Glue.ComponentParameter()

    @Glue.ComponentParameter
    def entry(self, pk: int | None) -> TimeEntry:
        if pk is None:
            return TimeEntry(date=self.day, user_id=self.request.user.pk)
        return TimeEntry.objects.active().get(pk=pk, user_id=self.request.user.pk)
```

```python
TimeEntryFormModalComponent(day=day)                  # a new entry
TimeEntryFormModalComponent(entry=entry, day=day)     # an existing one
```

```django
{% glue_component 'time_tracker/time_entry_form_modal' day=day %}
{% glue_component 'time_tracker/time_entry_form_modal' entry=entry day=day %}
```

**The annotation is the opt-in.**

- The key annotation admits `None` when it is a union that includes it:
  `int | None`, `Optional[int]`, `uuid.UUID | None`.
- A parameter whose key annotation does not admit `None`, or that has no key
  annotation, is unchanged from ADR 021: `None` raises
  `GlueComponentParameterError`. An initializer that was never written to receive
  `None` never receives it.
- Such a parameter is optional. A construction site that leaves it out gets a
  draft. It may also pass `None`, which means the same thing: reconstruction
  supplies the signed null that way, and one stamp can serve both cases when its
  argument is a row or `None`.
- A parameter that does not opt in stays required, as for any model parameter.

**The token signs a null key.** A draft's value in `target.parameters` is `null`.
Every later request calls the initializer with `None`, with the request bound and the
component's other parameters assigned, as ADR 021 describes for a key.

**An unsaved instance is still rejected.** Only the key is signed, so values set on a
supplied unsaved instance would be shown by the first render and gone on the next
request. A draft's contents come from the initializer alone, on the first render and
on every later one.

**A draft is seeded through the component's other parameters.** Values a draft
starts with, such as the record it belongs to or the day it is for, are passed as
their own parameters. They are signed, and the initializer reads them from `self`,
as `day` is read above.

A draft that needs several starting values the edit case does not takes them as
one optional parameter, so the edit case passes nothing extra:

```python
seed: EntrySeed | None = Glue.ComponentParameter(None)
```

- A dataclass parameter (ADR 021) restores its field types, so the initializer
  sees the same values on every request.
- A `dict[str, Any]` parameter is also accepted. It is signed as JSON, so a date
  or decimal in it is a string from the second request on. It suits a few strings
  or integers; a dataclass or a `TypedDict` suits anything else.
- Neither may hold a model instance. A related row travels as its key.

**A saved draft is signed by its new key.** The instance the initializer returned
for `None` is kept for the life of the object, as any resolved row is. When the
component's identity is next signed, a draft parameter whose resolved instance now
has a primary key is signed by that key. A callable that saves `self.entry`
therefore turns the component into one that edits the new record: the signed key
changes, the component re-renders, and later requests call the initializer with the
key.

- Glue sees only the instance the parameter resolved. A callable that creates and
  saves a different object assigns it to the parameter, as ADR 021 allows.
- The initializer remains a value provider. It must not save the draft it returns.

**Bounded parameters do not accept drafts.** A bounded initializer
([ADR 026](026-bounded-model-parameters.md)) whose key annotation admits `None`
raises `GlueComponentParameterError` at class definition, and the signed mapping
`{'model': ..., 'pk': None}` is rejected like any other malformed value. `None`
alone does not say which model a draft is of.

## Consequences

- A component that creates or edits a record declares one model parameter, with no
  separate key parameter or loader.
- The feature is additive. `None` was an error for every model parameter and remains
  one for a parameter that does not opt in.
- A construction site that forgets a draft parameter gets a new-record component,
  not an error.
- A draft parameter's initializer has two branches. Scope checks that apply to a
  saved row, such as the owning user, are written in the key branch; the draft
  branch sets the same values on the new instance.
- A stamped child's address fingerprints the parameters its stamp passes (ADR 025).
  A draft that is saved keeps its address for the rest of that request; a parent
  that then stamps it with the saved key stamps it at a new address, as for any
  parameter change.
- A callable that saves a draft always re-renders its component, even when it
  declares `skip_rerender=True` or returns a Glue object. The signed key changed,
  and ADR 022 re-renders whenever a signed value does, because the markup would no
  longer match the component's state.

## Rejected Alternatives

- **An argument on the decorator, such as `draft=True`.** The signature could then
  say `pk: int` while receiving `None`, and a model parameter would be configured in
  two places. The bounded form is already chosen by the signature alone.
- **Requiring the construction site to pass `None`.** It turns a forgotten
  parameter into an error instead of a new-record component. But
  `{% glue_component 'entries/entry_modal' entry=None %}` reads as though something
  is missing, and the declaration has already opted in to drafts, so leaving the
  parameter out is the natural way to ask for one.
- **A default of `None` on the key as the opt-in.** It says the same thing as the
  annotation in a second place, and an initializer with `pk: int = None` would
  receive a value its annotation denies.
- **Accepting an unsaved instance for the first render.** It mirrors "an instance is
  used as supplied", but nothing ties a supplied draft to the one the initializer
  builds, and they would differ from the second request on.
- **Signing the unsaved instance's field values.** Tokens are signed, not encrypted,
  so every signed column would be readable by the client and would need an explicit
  field list. Editable values that persist are what a `Glue.model` or form child
  holds; a parameter says which row.
- **Leaving the saved key to the application.** A callable that saved a draft and
  did not assign it back would build a fresh draft on the next request, and a second
  save would create a second record.
- **Drafts for bounded parameters, by passing the model class.** No use for one has
  come up, and it adds a third kind of value a construction site may pass. It can be
  added later without breaking anything.
