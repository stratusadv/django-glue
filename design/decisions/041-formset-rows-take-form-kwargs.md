# ADR 041: Formset Rows Take Form Kwargs

Status: Accepted

Date: 2026-11-12

## Context

Glue rebuilds a form on every request from what its token signs: the form
class, the saved record's key, the initial values and the editable fields. A
form built with constructor arguments is rebuilt without them. A single form
can often work around that through its instance: Profitly's `AccountForm`
narrows its `parent` choices to the account's company through
`self.instance.company_id`. A new formset row has no saved instance to read.

Profitly's journal entries (PROF-31) hit this. Each line of an entry is a row of
`JournalLineForm`, and its `account` must be one of the company's accounts. The
row cannot be told the company, so `account` became a plain `IntegerField`. The
component offers the company's accounts itself and checks every chosen id
against them in its action. As a `ModelChoiceField` over every account, the field
would also have let `foreign_key_choices()` list other companies' accounts.

Django formsets answer this with `form_kwargs`, passed to every row's
constructor, and `get_form_kwargs()`, which a formset overrides to compute them.
The second matters for cost. A row that looks its choice up with its own query,
as `ModelChoiceField` does, costs a query per row on every call. Rows that share
choices loaded once by their formset cost one.

## Decision

A formset takes `form_kwargs`, signs them, and builds every row form with them.

1. **`form_kwargs` are plain values, signed.** `Glue.FormSet(...)` and
   `Glue.formset(...)` take `form_kwargs`, a mapping of values the token
   serializer can sign. A related record is passed as its key. A value that
   cannot be signed is refused with `TypeError` when the formset is built.

   ```python
   JournalLineFormSet(access=Glue.Access.ADD, form_kwargs={'company_id': company.pk})
   ```

2. **Every row form is built with them.** Seeded rows, `extra` rows, appended
   rows and rows rebuilt from their tokens all receive `form_kwargs` as keyword
   arguments, and so does each form bound to validate them. A form passed in
   `instances` is built by its caller, who passes the same arguments.
3. **Each row signs them too.** `FormGlue` signs the `form_kwargs` it was built
   with in its identity, so a row rebuilt on its own, for one of its own calls
   such as `foreign_key_choices()`, is built with them as well.
4. **`get_form_kwargs()` derives values once per request.** It returns the
   arguments the formset builds its rows with: `form_kwargs` unless a subclass
   adds to them. An override may add values derived from `form_kwargs`, such as
   the rows every form looks its choice up in, and keeps `form_kwargs` itself.
   Derived values are not signed. A row rebuilt on its own is built with only the
   signed `form_kwargs`, so its form must work without the derived ones.
5. **`Glue.form()` does not take them.** No application needs constructor
   arguments on a single glued form yet; a saved instance has carried what they
   need.

## Consequences

- A row form can narrow a choice field by what the server knows, as any Django
  form does, so a relation on a row is an ordinary `ModelChoiceField` again and
  `foreign_key_choices()` offers only the narrowed rows.
- A formset can keep its rows' validation constant in the number of rows by
  loading shared choices once in `get_form_kwargs()`.
- The identity of every form gains `form_kwargs`, empty unless given, so tokens
  issued before this change no longer verify. This is a release boundary, as any
  identity change is.
- The tests: each way a row is built receives `form_kwargs`; the formset and each
  row sign them; a row rebuilt on its own is built with them; derived values are
  made once per request, reach rows built, rebuilt and bound, and are not signed;
  a value that cannot be signed is refused.

## Rejected Alternatives

- **Signed `new_row_defaults` read as constructor input.** It works today, but a
  default is a field's starting value. A form that reads a key that is not one of
  its fields from `initial` hides a constructor argument in the wrong place.
- **Reading the request inside the form.** Profitly's middleware puts the company
  on the request, but a form that reaches for the request, through a thread-local
  or otherwise, depends on ambient state its callers cannot see.
- **Derived values signed in the token.** Querysets and records cannot be
  signed, and a token that carried a company's accounts would grow with the
  company.
