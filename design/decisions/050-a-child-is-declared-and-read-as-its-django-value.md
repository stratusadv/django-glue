# ADR 050: A Child Is Declared And Read As Its Django Value

Status: Proposed

Date: 2026-11-22

## Context

A child (`@Glue.child`, ADR 034) is declared by a method that returns a Glue
object, and reading the child returns that object:

```python
@Glue.child
def filters(self) -> Glue.Form:
    return Glue.form(target=JournalEntryFilterForm(company=self.request.company), access=Glue.Access.CHANGE)

def get_queryset(self):
    if not self.filters.is_valid():
        ...
    filters = self.filters.cleaned_data
```

The Glue object is the child's island: its signed token, its access and the
calls the browser makes on it, such as `foreign_key_choices` searching a
`ModelChoiceField`. Application code needs none of that. It needs the form.

- **Declaring a child wraps the form in `Glue.form(...)`.** The wrapper's
  `unique_name` comes from the method's name, and its `form_kwargs` are
  replaced by the form's own `initial`. What remains is `access` and
  `editable`. Of the eight form children in Profitly and django-spire, seven
  pass `access=self.access`, the owner's access, and none passes `editable`.
- **Reading a child returns the wrapper, which imitates a form in part.**
  `FormGlue` copies `is_valid()` and `cleaned_data`, but it has no `errors`,
  `fields` or `has_changed()`, its `cleaned_data` raises before validation,
  and the form itself is at `bound_form`, which is `None` until validation
  runs. Every Python read of a form child in Profitly and django-spire uses
  only `is_valid()` and `cleaned_data`, except one that reaches through
  `bound_form` to read the form itself.

So application code builds a Django form, hands it to a wrapper, and reads
back an imitation of it.

## Decision

A child is declared by returning its Django value, and is read as its Django
value. The Glue object stays the child's island, built and kept by Glue, and
application code does not see it.

1. **A child's method may return a Django value.** A value of a type a Glue
   object is registered for is wrapped in that Glue object, under the child's
   name and with the options its decorator gives. A form is wrapped in a
   `FormGlue`. Returning a Glue object, such as `Glue.form(...)`, still works,
   and that object is used as it is.

2. **`@Glue.child` takes the wrapper's options.** Written bare or with
   arguments, it takes the options of the Glue object the child's return
   annotation is registered with: for a form, `access` and `editable`, as
   `Glue.form` takes them. The annotation names the Django class (`->
   JournalEntryFilterForm`), so options the wrapper doesn't take are refused
   when the class is defined. A method that returns a Glue object under a
   decorator with options is refused: a setting has one place.

3. **A child returned bare takes its owner's access.** With no `access`, it
   has the access its owner has, so it can never do more than the user its
   owner serves. A child that must do more says so, such as filters a viewer
   may change: `@Glue.child(access=Glue.Access.CHANGE)`. A child that returns
   a Glue object keeps the access that object was given.

4. **Reading a form child returns the Django form.** It is the form bound to
   the values the browser submitted, or, with nothing submitted, to its own
   initial values, so it validates on the first render. It is built with its
   `initial` and any arguments Glue keeps for it (ADR 041), and Django
   validates it only when application code asks, as for any form. This holds
   however the child was declared. The child's island presents the errors of
   the form it handed out, when validation ran, so the browser shows them as
   it shows a `validate()` call's today.

5. **A Glue object plugs in through a registry.** The child descriptor never
   names a kind of Glue object. Each Glue object that can be returned bare
   registers the Django type it wraps, the options it takes, and what reading
   the child returns. `FormGlue` registers for `forms.BaseForm`. A child of a
   type with no registered Glue object is refused when its class is defined,
   and reads as the Glue object it returns.

```python
class JournalEntryListComponent(QuerySetScrollComponent):
    @Glue.child(access=Glue.Access.CHANGE)
    def filters(self) -> JournalEntryFilterForm:
        return JournalEntryFilterForm(company=self.request.company)

    def get_queryset(self) -> JournalEntryQuerySet:
        if not self.filters.is_valid():
            ...
        filters = self.filters.cleaned_data
```

```python
class PayableDocumentFormComponent(Glue.Component):
    @Glue.child
    def document_form(self) -> PayableDocumentForm:
        return self.form_class(company=self.request.company, initial={...})
```

### Models and querysets

This record registers forms only. A model or a queryset child plugs in through
the same registry when a project needs one, and until then is declared with
`Glue.model(...)` or `Glue.queryset(...)` as it is now. Its registration must
require `fields` or `exclude` from the decorator, and refuse a child given
neither: Glue can't choose which fields to sign and send, and sending every
field would publish columns no one chose to show.

Formsets are already declared as their own Glue class (`Glue.FormSet`,
ADR 012), which is the value application code returns and reads, so this
record doesn't change them.

## Security

- **A bare child can do no more than its owner** unless its declaration says
  so (rule 3), where a `Glue.form(...)` child is at `CHANGE` unless it says
  otherwise.
- **The island's authority is unchanged.** The child's token, its access, its
  calls and the checks on its submissions (ADRs 034 and 049) are those of the
  Glue object, which is built as `Glue.form(...)` builds it. The form handed to
  application code grants nothing: changing it in Python changes no token.
- **Model and queryset children must name their fields** when they are added.

## Consequences

- Component code works with Django forms: `is_valid()`, `cleaned_data`,
  `errors`, `has_changed()`, and a form's own attributes, without
  `bound_form`.
- `FormGlue` keeps its `is_valid()` and `cleaned_data` for the Glue objects
  views build with `Glue.form(request, ...)`. Glue's tests that call them on a
  child read the form instead.
- Application code has no route to a child's Glue object. None needs one: no
  Python code in Profitly or django-spire calls `validate()`, `save()` or
  another Glue method on a child. A component that needs one returns the
  Glue object, and still reads the form.
- `@Glue.child` written bare keeps working, so existing declarations change
  only when their author moves them to a bare return.
- In Profitly, each form child becomes a bare return. The journal filters
  declare `access=Glue.Access.CHANGE`, and the payment component reads
  `self.payment_form.allocations` instead of reaching through `bound_form`.
- The tests:
  - a bare form child is wrapped with the decorator's options, and with its
    owner's access when none is given;
  - an option the annotation's Glue object doesn't take is refused when the
    class is defined, as are an annotation with no registered Glue object
    and a returned Glue object under a decorator with options;
  - reading a form child returns the form, bound to the submission or to its
    initial values, with its `initial`, in a call, a render, a refresh and the
    re-render after a call (ADR 049);
  - errors from validating that form reach the browser;
  - a child that returns `Glue.form(...)` reads as the form too.

## Rejected Alternatives

- **A flag on `@Glue.child` that makes a read return the form.** One
  declaration would then read as one of two types depending on a setting,
  and no caller wants the Glue object.
- **`@Glue.form` as a decorator in place of `@Glue.child`.** A decorated
  method always receives the component, so it would not separate children
  that need the instance from those that don't. `Glue.form` would build a
  Glue object or return a decorator depending on its arguments, and models,
  querysets and formsets would each want a decorator of their own. One
  `@Glue.child` takes each kind's options, and the annotation names the kind.
- **A form held as state (ADR 042) for forms with no island.** Its form is
  rebuilt from its field values alone, so it keeps no `initial` and refuses a
  field over a queryset, and it has no call to search its choices. A form
  that needs the request is a child (ADR 049).
