# ADR 042: A Serializer Carries A Value Both Ways

Status: Accepted

Date: 2026-11-13

## Context

A value crosses between Python and the browser in four places: an attribute's
value going out, an update or a signed value coming back, a callable's
argument, and a component's parameter. Five mechanisms shared that work, and
none owned it:

- **`GlueSerializerHandler` and its registry** converted values coming in. A
  handler was found for every value by asking each one `supports()`. `decode`
  repeated `coerce` in two of the three handlers, and `encode` and `prepare`
  did something in one.
- **`GlueResponseJSONEncoder`** converted values going out, by the type each
  value happened to have. The declared type was not consulted.
- **`GlueAttributeAdapter`** described a field to the browser and also
  converted it, and the converting half passed straight through to the
  registry.
- **`BoundGlueAttribute`** chose between them: the adapter, else the type
  hint, else a guess from the current value.
- **`GlueValueAdapter`** turned an assigned list into a `SequenceGlue`. It
  shared a name with the other adapter and nothing else.

The flaw underneath was that in and out were different systems. A value coming
in was converted by its declaration; a value going out had to be JSON already,
because `BoundGlueAttribute.get()` refused anything else and `encode` was only
ever called for component parameters. So an attribute could not hold an object
that is not its own wire form.

That is what Profitly's chart of accounts needed. Its list is filtered by a
search, a multi-select of account types and a sort, read while the component
renders its rows on every path: the first render, a call, a refresh and the
re-render after a call (ADR 022). Those are a Django form's job, and the
component's own state is the only state that holds on all four paths. A child
form (ADR 034) was tried and does not fit: a component sees a child's changes
only inside a call that submitted it, a refresh carries no children, and
outside a submission each read of a child runs its initializer again. ADR 034
recorded the gap, rejecting "field values as editable state on the component"
because it gave up Django forms.

Livewire answers the same need with one concept. Every property passes through
a synthesizer chosen by its type, which dehydrates the value into the
snapshot and hydrates it back, and a form object is one synthesizer among the
others: one property whose state is its fields.

## Decision

Each declaration has one serializer, a `GlueSerializer`, which carries its
values in both directions. It replaces the serializer handlers, and takes the
converting half of the attribute adapter.

```python
class GlueSerializer(ABC):
    def __init__(self, target): ...          # the declaration: a type hint, or a field
    @classmethod
    def supports(cls, target) -> bool: ...
    def load(self, raw): ...                 # what the browser sent, or Python assigned
    def restore(self, raw): ...              # what a signed token holds; loads by default
    def dump(self, value): ...               # the wire form; the value itself by default
    def default(self): ...                   # an attribute's value when it declares none; None
    def check(self): ...                     # refuse a declaration before any value arrives
    def description(self, *, read, editable): ...   # none by default (rule 5)

glue_serializer_registry.register(MySerializer)
glue_serializer_registry.resolve(target)     # the first registered class that supports it
```

1. **A declaration's serializer is resolved once.** The collector resolves a
   value attribute's type hint and each callable argument's annotation when it
   compiles the class, and stores the serializer on the definition. A
   declaration built at runtime has no hint, so `Glue.attr(value_type=...)`
   names its target: a glued form or model passes each field. An attribute
   with no declared type still takes the serializer of the value it holds.
2. **Everything that crosses uses it.** An update is `load`ed, a signed value
   is `restore`d, a callable argument is `load`ed (ADR 038), and a component
   parameter is `load`ed, `dump`ed into its identity and `restore`d. The two
   differ only where a signed value must be accepted that the browser may not
   send, which today is a file field.
3. **An attribute's value goes out as it is when the wire encoder can write
   it, and is `dump`ed by its serializer when it cannot.** So every value that
   was sent before is sent byte for byte as before, in Django's formats, and a
   value that used to be refused as not JSON now crosses if its type can dump
   it. `BoundGlueAttribute.get()` returns the Python value, and
   `wire_value()` returns what is signed and sent.
4. **The built-in serializers** are the type hint (`AnnotationSerializer`, by
   pydantic), the model field and the form field, which live with the Django
   objects and register themselves, and the form class (rule 6).
5. **A description says how to draw a control, and converts nothing.**
   `GlueAttributeAdapter` becomes `GlueFieldDescription`, with `schema()` and
   `computed_data()` only, supplied by the owner's `get_field_descriptions()`.
   A serializer may describe its own values through `description()`, which the
   owner uses for an attribute it gave no description of. The description is
   handed a way to read the value and whether it is editable, and nothing else
   of the owner.
6. **A form class has a serializer.** An attribute typed as a Django form holds
   the form, bound to its values. On the wire it is one value, an object of
   the fields' values, signed and updated whole as any editable value is.

   ```python
   class AccountListComponent(ModelCrudScrollComponent):
       filters: AccountFilterForm = Glue.attr(editable=True)

       def get_queryset(self) -> AccountQuerySet:
           if not self.filters.is_valid():
               ...
           account_types = self.filters.cleaned_data['account_types']
   ```

   ```django
   {% include 'django_spire/glue/form/field/choice/multiple_search_field.html'
       with glue_field='component.filters.account_types' %}
   ```

   - Every read in a request returns the same form, so `is_valid()` and then
     `cleaned_data` work on one object.
   - An attribute that declares no default starts as the form class called
     with no arguments: the serializer's `default()`, which is `None` for every
     other serializer, so no other attribute's value changes.
   - An unbound form, whether that default, a declared one or one assigned in
     a call, is bound to its own initial values, so it validates before the
     browser has sent any.
   - The form describes each of its fields as a glued form does. The client
     reaches them as `owner.attribute.$fields.<name>`, so Spire's field
     templates bind unchanged, and each field reads its errors from a
     validation that already ran. Glue never runs one to report errors.
   - A form with a file field, a write-only field (ADR 036) or a field over a
     queryset is refused when its class is first used. The form is built from
     its values alone, so nothing could narrow a queryset to what the request
     may see.
   - A model form with no instance is a form like any other, and offers no
     save. A model form over a saved record is refused: editing a record is a
     child's job.
   - A form class also types a callable's argument, which arrives as the form
     bound to what the browser sent.

`Glue.child` keeps everything that is an object with its own identity: a form
over a saved record, a formset, a form with callables or events of its own,
and a nested component. The rule for choosing: when the owner renders from the
values, they are a form-typed attribute; when a call consumes them, or the
form edits a record, has rows or has actions of its own, it is a child.

## Consequences

- **Breaking: a serializer is written differently.** `GlueSerializerHandler` is
  `GlueSerializer`: `supports` is a classmethod, `coerce` is `load`, `decode`
  is `restore`, `encode` is `dump`, `prepare` is `check`, and each reads its
  target from `self.target`. The registry keeps its names,
  `GlueSerializerRegistry` and `glue_serializer_registry`, but registers a
  class and answers `resolve(target)`, where it used to convert a value
  itself. `GlueSerializerError` is unchanged.
  `BaseGlue.get_attribute_adapters()` is `get_field_descriptions()`, and an
  adapter's `coerce` and `decode` are removed. Spire, Profitly, Showcase and
  the Stratus portal use none of these.
- No value that crossed before crosses differently. Model and form fields,
  untyped attributes, callable arguments and component parameters keep their
  formats, and their tests pass unchanged.
- An attribute can hold a dataclass, a non-string enum or any other value its
  type hint can dump, where before it had to be JSON already.
- A default is now adapted as an assigned value is, so a default list with a
  `glue_factory` becomes a `SequenceGlue` as an assigned one does.
- A change to one field of a form held as state sends the whole form's values.
  It suits a few fields; a large form belongs in a child.
- A form-typed attribute's description depends on its type hint resolving at
  runtime. When a class's hints do not resolve, the form still crosses, by the
  type of the value it holds, but it describes no fields.
- In `ModelGlue` and `FormGlue` the declaration of an editable field names the
  field that types it, and the field's description only describes.
- The tests: a serializer loads, restores and dumps; every earlier test of
  updates, arguments, parameters and field payloads passes unchanged; a form
  held as state is bound before the browser sends anything, is one object per
  request, describes its fields, takes an update, holds through a refresh and
  a later request, reports field and whole-form errors only after a
  validation, refuses state that is not its fields, is rebound when an unbound
  form is assigned, types a callable argument, and is refused with a file,
  write-only or queryset field or over a saved record; and on the client its
  fields are reached beside its value, are not sent with it, send the whole
  value when one changes, and read their own errors.

## Rejected Alternatives

- **A composite type that expands one declaration into an attribute per
  field.** It was designed first, as a seam beside the serializer and the
  adapter. It needed a new attribute kind, dotted paths under a value, a
  registry rule for them and a second form-field adapter, all to work around
  the outbound path being untyped. Typing that path removes the need.
- **A form serializer in the old registry.** The registry converted inbound
  values only, so the form could not have gone out.
- **Dumping every typed attribute through pydantic.** It would send
  microseconds where Django's encoder sends milliseconds, and a shorter
  `timedelta`, for attributes only: model and form field values would keep
  Django's formats, so one page would show two.
- **Folding the description into the serializer.** A description needs its
  owner: whether the field is editable, the request, the validation's errors.
  A callable argument and a component parameter have a type and nothing to
  describe.
- **`BaseGlue` as a serializer, or a child as an attribute whose type is a Glue
  object.** A serializer describes a kind of value inside its owner's state. A
  Glue object is one addressed instance with its own token, access and
  lifecycle (ADR 034), and its wire form is a separate entry, not a value.
- **A child form read outside calls.** It needs a child initialized once per
  component, children carried by refresh, and re-renders rebuilt from each
  child's successor token: three changes to how components see children, for
  state the component already knows how to keep.
- **Model forms with an instance, and models, as state.** Editing a record
  needs its pk signed, the record loaded on every request and a save, which
  `FormGlue` and `ModelGlue` already do as children.
- **A single form field as an attribute's type.** A one-field form covers it,
  and keeps one way to declare form-shaped state.
