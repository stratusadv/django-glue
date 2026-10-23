# ADR 028: Formsets Edit Saved Records

Status: Accepted; implemented on branch

Date: 2026-10-06

## Context

[ADR 012](012-formset-is-a-keyed-collection.md) made `FormSetGlue` a keyed
collection of `FormGlue` children. It also decided that the collection starts
empty, and it carried `can_delete` only as part of the formset's identity. A
formset could therefore collect new rows, but it could not show records that
already exist, and removing a row had no effect on the database.

The driving case is editing a parent's child records in one place: an order's
line items, a gorilla's skills. The page loads with the saved records as rows.
The user edits some, adds some, removes some, and saves once.

Two things were missing:

- **Seeding.** There was no way to construct a formset with rows already in it.
- **Deletion.** `pop` removed a row from the formset's membership and forgot it.
  `save` saved the rows that were left. A removed record stayed in the database
  and came back on the next page load.

Deletion has a constraint the rest of the formset does not. The server keeps no
state between requests, and removing a row and saving are separate requests. The
decision to delete a record has to survive from one to the other.

## Decision

**A formset may be seeded with saved records and with prefilled blank rows.**

```python
Glue.formset(
    request,
    'skills',
    SkillForm,
    Glue.Access.DELETE,
    instances=gorilla.skills.all(),
    initial=[{'difficulty': 3}],
    can_delete=True,
)
```

- `instances` takes saved model instances, or unbound forms of the formset's
  form class. An instance requires a `ModelForm` and is wrapped as
  `form_class(instance=instance)`. An unsaved instance, an instance of another
  model, a form of another class, and a bound form are each rejected at
  construction.
- `initial` takes one mapping per prefilled blank row.
- Rows are keyed `'0'`, `'1'`, ... in order, instances first. The client continues
  from the highest key when it appends.
- Seeded rows pass through the same admission as appended rows, so a seed larger
  than `max_num` is rejected at construction.

This supersedes ADR 012's statement that the collection starts empty. Everything
else in ADR 012 stands: no `BaseFormSet`, keyed membership, and `min_num` /
`max_num` as validation bounds, not a count of blank rows to create.

**The server sets a new row's starting values; the client may only prefill what
a user can edit.** A row added in the browser belongs to something the form does
not expose: the order whose line it is, the gorilla whose fight it is. A formset
rebuilt on a later request knows its form class and its rows, not the record
that owns it, so that value has to travel with the formset.

```python
Glue.FormSet(
    LineForm,
    instances=order.lines.all(),
    new_row_defaults={'order': order.pk},
    access=Glue.Access.DELETE,
    can_delete=True,
)
```

- `new_row_defaults` is a mapping of field name to value. It is signed into the
  formset's identity, next to `min_num`, `max_num` and `can_delete`.
- It is merged over the initial values of every row that has no saved record: a
  row seeded with `initial`, an unbound form passed through `instances` that has
  no saved record, and a row the client appends. The server's value
  wins over the client's `initial`. From there it is signed into the row's own
  token like any initial value and set on the unsaved record when the row is
  saved.
- A default is fixed exactly where the user cannot edit the field: a model field
  the form does not expose, or a form field with `disabled=True`. The client
  cannot send an update for either, so the default is what is saved. Carrying an
  owner key this way is the purpose of the argument.
- A default on a field the user can edit is a starting value. It prefills the
  input, and what the user types is saved. An owner key must therefore never be
  an editable field of the row form.
- `append(key, initial)` rejects any `initial` key that is not an editable field
  of the form, with `invalid_kwargs`. Before this ADR it accepted every key, so a
  client could set a model field the form withheld, including the owner.

This is the rule `QuerySetGlue.new(initial)` already follows: `initial` is
untrusted and each key must be admitted by what the client may edit.

**Removing a saved row records its deletion; `save` performs it.** `pop` appends
the row's primary key to the formset's pending deletions. Those are signed into
the formset's token as `state_snapshot.removed_pks`, present only when the list
is not empty. `save` deletes the recorded records and clears the list. Removing a
row that was never saved records nothing.

Until `save` runs, the record is untouched. Reloading the page discards the
pending deletion along with every other unsaved edit.

**`pop` receives the removed row's own token.** The formset's token carries each
row's address but not its primary key, which is in the row's token. The client
therefore submits that one row with `pop`, under the same `__submitted_forms`
key that `validate` and `save` use for every live row. The server verifies it as
it verifies any submitted row and reads the primary key from the rebuilt form.
The client sends the row without its unsaved edits, so a value that cannot be
coerced does not block removing the row.

A recorded primary key always comes from a row token this server signed for this
formset. A client cannot name a record the application did not put in the
formset.

**Removing a saved row requires `DELETE`; removing an unsaved row requires
`ADD`.** The check runs in `pop`, before anything is recorded, so a refused
removal leaves the row on the page.

**The other actions ask by whether a record is saved, as a single form does
(ADR 009).** `append` requires `ADD`. `validate` and `save` require `ADD` while
every row is new, and `CHANGE` once the formset holds a saved record or has
removed one. Until 1.3.0 all four required `CHANGE`, so a formset that only
creates rows could not be used with `ADD` access, and its owner had to give it
more access than the user had.

**`save` is all-or-nothing.** It validates every row first. If any row is
invalid it saves nothing, deletes nothing, and returns `{'valid': False}`, and
each invalid row carries its own errors. Otherwise it saves the rows and applies
the deletions in one transaction.

**Two hooks replace the writes.** Both run inside that transaction, and both are
overridden on a `Glue.FormSet` subclass, as `clean()` is. The `save_forms` below
saves each row through a [django-spire](https://django-spire.stratusadv.com)
model service; `services.save_model_obj` is django-spire's, not Glue's.

```python
class LineFormSet(Glue.FormSet):
    form_class = LineForm
    can_delete = True

    def save_forms(self, form_list):
        for form in form_list:
            form.instance.services.save_model_obj(**form.cleaned_data)

    def delete_removed(self, queryset):
        queryset.update(is_deleted=True)
```

- `save_forms(form_list)` receives the validated Django forms of the remaining
  rows. The default calls `form.save()` on each form that has one, skipping a
  saved record whose form has not changed. A row that was never saved is always
  written, so a prefilled row the user did not edit is still created.
- `delete_removed(queryset)` receives a queryset of the removed records. The
  default calls `queryset.delete()`.

**Submitted rows are loaded together.** The formset verifies every submitted
row's token, loads all their records in one query, with one more for each
many-to-many field the form exposes, and then rebuilds the rows. The number of
queries the formset runs to load its rows does not grow with the number of rows.

Django's own validation is unchanged, and it still queries per row. For each
foreign-key field a form exposes, `ModelChoiceField` fetches the related record
and `ForeignKey.validate` checks that it exists, so `validate` and `save` cost
two queries per foreign-key field per row, as a Django model formset does.
Unique constraints are checked per row the same way. An application that needs
fewer leaves the relation off the row form and sets it with `new_row_defaults`.

The wire key for submitted rows is renamed from `__forms` to `__submitted_forms`.
It names unverified row payloads from the client, which the old name did not
distinguish from the formset's own list of rebuilt forms.

## Consequences

- One formset can load, edit, add to, and remove from a set of saved records, and
  persist all of it with one `save`.
- A removal is a draft like any other edit. It is not applied until `save` and is
  lost on reload.
- A component may declare a formset as a `@Glue.property` child and give it more
  access than the component has, for example `DELETE` on the lines of an order
  the component may only `CHANGE`. A declared child's access is not capped by its
  owner's. The cap applies to an object a callable returns.
- A formset's identity gains `new_row_defaults`. Its values must be ones a token
  can sign, so an owner is passed as its primary key, not as an instance.
- A client that passed `append` an `initial` key outside the form's editable
  fields is now rejected. A page that relied on that to set an owner key declares
  `new_row_defaults` instead.
- The formset's token grows by one primary key per pending deletion.
- `pop` costs one query, to rebuild the removed row. It does not rebuild the
  other rows.
- `FormSetGlue.save()` no longer calls `FormGlue.save()` on each row. It validates
  each row and hands the bound Django forms to `save_forms`.
- A formset with one invalid row saves none of its rows. Before this ADR it saved
  the valid ones.
- The default `delete_removed` is a bulk delete. It does not call a model's
  `delete()` override, as any queryset delete does not. A model that needs it
  overrides the hook.
- `save` does not run `clean()` or the `min_num` / `max_num` checks. It did not
  before this ADR either. An application that needs them calls `validate()` from
  its own save action.
- A client built before this ADR calls `pop` without the row's token and is
  rejected.
- `validate` and `save` read their rows in a fixed number of queries, and `save`
  writes one query per changed or new row. Before this ADR each row cost a read
  and a write whether or not it had changed. The queries Django's validation
  runs for a form's foreign-key and unique fields still grow with the rows.
- Saving is last-write-wins, as it is for a Django model formset. "Changed" is
  judged against the record as it is now, and a row the user did not edit still
  carries the values it had when the page loaded. If another request changed
  that record in the meantime, the row counts as changed and `save` writes the
  page's values over it. This differs from `ModelGlue`, which records the fields
  the user edited in `$draft` and lets the fetched row win for the rest.

## Rejected Alternatives

- **Deleting the record in `pop`.** It needs no retained state. But a removal
  would take effect immediately while every other edit waits for `save`, and the
  user could not back out by leaving the page.
- **Holding the removed row's verified token on the formset between
  `process_attribute_call` and `pop`.** It avoids the query. It adds an attribute
  that exists only to pass a value between two methods and that is `None` the
  rest of the time. Rebuilding the row uses the path every other call already
  uses.
- **Submitting every live row with `pop`.** It needs no change to how rows are
  submitted. It uploads every row's token and rebuilds every row's form to
  remove one.
- **Signing each row's primary key in the formset's token from the start.** `pop`
  would need no row token. It duplicates what each row's token already signs, and
  the formset would have to keep the copy current as rows are first saved.
- **Deriving a child formset's access from its owner's.** "Changing an order may
  delete its lines" is true of some reverse relations and false of others, such
  as a customer's orders. The component that builds the formset states its access.
  This matches the rule for relation querysets, which never receive implicit
  `CHANGE` or `DELETE`.
- **An `owner=` argument naming the parent and its foreign key.** It reads well
  for the one case, as Django's inline formsets do. It cannot carry a second
  fixed value, such as a tenant or a type, and it makes the formset reason about
  relations. A plain mapping covers the owner and the rest.
- **Exposing the owner as a form field the client fills in.** The client could
  then name any owner.
- **A separate `is_authorized()` question for the deletion.** The signed access
  level already separates discarding a draft from deleting a record, and
  `is_authorized()` is already consulted for every `pop`.
