# ADR 034: `Glue.child` Declares A Child, And A Component's Calls Carry Its Writable Children

Status: Accepted; implemented on branch

Date: 2026-10-10

## Context

Profitly's invoice builder is one page that creates a customer, an invoice and
its lines in a single step. It needs a header form and a formset of lines to be
validated together and saved together: if a line is invalid, nothing is saved,
including the customer.

Glue had no way to write that. Each Glue object is reconstructed from its own
token and carries its own edits, so a component's call could not see what the
user had typed into the component's own form children. The builder worked
around it by keeping every field in hand-written Alpine state, passing it all
to one call as arguments, and parsing and validating it by hand on the server.
None of Glue's form handling was in use on a page that is entirely a form.

The alternatives a project had were no better. Saving each form with its own
call is not atomic. Putting every field on the component as editable state
gives up Django forms. The portal's bulk time-entry modal avoids the problem
only because it has a single formset and nothing beside it.

Separately, a child was declared with `Glue.property` and a Glue-object return
annotation. That gave `Glue.property` two unrelated jobs chosen by the
annotation: a computed, read-only value, and a child slot whose method is an
initializer that does not run on every read. The second was never a property,
and the specification already called it a "factory for introduction, not a
derivation".

## Decision

**`Glue.child` declares a child Glue object.** The decorated method initializes
the child, and its return annotation names the Glue object:

```python
class InvoiceBuilderComponent(Glue.Component):
    @Glue.child
    def header_form(self) -> FormGlue:
        return Glue.form(target=InvoiceHeaderForm(), access=Glue.Access.ADD)

    @Glue.child
    def lines_form(self) -> InvoiceLineFormSet:
        return InvoiceLineFormSet(access=Glue.Access.ADD)
```

A missing annotation, or one that does not name a Glue object, raises
`TypeError` when the class is defined. In every other respect the slot is the
one a typed `Glue.property` compiled: the same address, token, nullability and
lifecycle.

**A component's call carries each of its `Glue.child` children that the user
may change.** A child with any access above `VIEW` is sent with every call the
component makes: its own signed token and the user's unsaved changes, and for
a formset its rows. Reading the child during that call returns it rebuilt from
that token with the changes applied, so one call can check and save several
children together:

```python
@Glue.attr(required_access=Glue.Access.ADD)
def send_invoice(self) -> Glue.Response | None:
    if not all_valid([self.header_form, self.lines_form]):
        return None

    header = self.header_form.cleaned_data
    ...
```

There is no option to turn this on. It follows from two things the child
already has: its slot on the component and its access.

Four rules bound it:

1. **A submission is checked when the call reads the child, and not before.** A
   call that reads no child ignores whatever was sent with it, so a call that
   worked before cannot start failing because an unrelated child's token
   expired.
2. **A read child must be the one signed into the slot.** The submitted token
   must verify for this request's session and user, its address must be the
   address the component's own token records for that slot, and its access
   must be above `VIEW`. Anything else fails the call with
   `invalid_child_submission`.
3. **Every read of a submitted child in one call returns the same object.** A
   child validated on one line is the validated child on the next.
4. **A read child answers in the same response.** Its own entry is returned
   with the call's, so what it derived from the user's changes, such as a
   form's errors, reaches the browser without a second request.

A refresh carries no children: it runs no application code that could read
them.

**`Glue.property` returning a Glue object is deprecated.** It warns with
`DeprecationWarning` and otherwise behaves exactly as before, and such a child
is never submitted with its component's calls. In django-glue 2.0
`Glue.property` only computes values. Glue's own built-in children (a model's
projected relations and named forms) are declared with `Glue.child`.

## Consequences

- A composite form is an ordinary component: `Glue.child` forms, and one call
  that reads them. Validation stays in Django forms and field errors appear
  under their fields.
- The submission is untrusted and grants nothing. The child's own signed token
  is the authority for what may change, exactly as when the child is addressed
  directly. A client that omits a child only makes the call read a blank one.
- A call on a component with writable children is larger: it carries every
  such child whether or not the call reads it. The browser cannot know which a
  call will read, and a formset cannot be skipped as "unchanged" because its
  row membership lives in its token.
- A file chosen in a submitted child's field is not carried. Only the
  component's own file uploads travel with its calls.
- An error that belongs to a formset as a whole, not to a field, is recorded
  by the browser only when the formset's own `validate()` is called.
- Outside a submission, each read of a child runs its initializer again and
  returns a new object. A call made with no browser, as in a unit test that
  submits nothing, must not assume two reads are the same child.
- Only a component's direct children are submitted, a formset's rows included.
  A queryset's rows and children of children are not.
- Existing children keep working. The five components that declared a child
  with `Glue.property` when this was written (django-spire's `FormComponent`
  and `ModelFormComponent`, the portal's bulk time-entry modal, and two in
  Glue's test project) warn until they move. None of them has a call that
  reads its child, so moving them changes only the size of their calls.

## Rejected Alternatives

- **A form-group Glue object, or a multi-form component in django-spire.** A
  new family, or a generic component with a declarative interface for its
  forms. The gap was that a call could not see its children, and closing that
  made a plain component enough.
- **An option on the declaration**, tried as `Glue.property(bind=True)`,
  `Glue.child(bound=True)` and `submit=True`. Each named the same fact the
  child's access already states, and added a setting to explain and to test in
  combination with access.
- **`Glue.attr(editable=True)` on the method.** The closest in meaning: the
  browser edits it and the server sees the edits. But `Glue.attr` on a method
  declares a callable, so the flag would have had to change what the decorator
  declares.
- **Keeping the child on `Glue.property`.** It works, and the submission rule
  does not depend on the spelling. It leaves a property that is written to and
  whose body does not run on every read.
- **Submitting only the children the user changed.** Smaller requests, but a
  formset's appended and removed rows are not visible as field changes.
- **Checking every submitted child on arrival.** Simpler than checking on
  read, but it makes every call depend on the validity of children it never
  uses.
- **Field values as editable state on the component.** No Glue change at all,
  at the cost of Django forms: validation, cleaning and error placement would
  be hand-written per page, as the builder's were.
