# Forms

`Glue.form()` wraps a configured Django `Form` or `ModelForm` as a form
object. A model form remains a form proxy; it does not silently become a
model object.

```python
Glue.form(
    request=request,
    target=ContactForm(),
    unique_name='contact',
    access=Glue.Access.CHANGE,
    editable=['name', 'email', 'message'],
)
```

```javascript
const form = Glue.form.contact
form.name = 'Ada'
form.email = 'ada@example.com'
await form.validate()
if (!form.$fields.email.errors.length) await form.save()
```

The proxy exposes declared fields as editable properties. `$fields` contains
field descriptions and current validation errors. An invalid `validate()` or
`save()` acknowledges the submitted draft and returns errors without turning
the draft into a server-side session object. A successful model-form save
advances its target identity in the successor policy.

`editable=` limits which declared form fields accept browser updates. Choice
fields remain scalar or flat-list values on the wire; Glue rejects nested
objects in their place. File inputs travel as multipart file parts.

`Glue.formset()` creates a keyed collection of form children from an importable
form class or `Glue.FormSet` subclass. It does not wrap a Django `BaseFormSet`
instance or a `formset_factory()` class. Configure cross-form behavior on a
subclass:

```python
class EntryFormSet(Glue.FormSet):
    form_class = EntryForm
    min_num = 1
    max_num = 50
    can_delete = True
```

The collection starts empty unless it is seeded. Call
`await formset.append(initial)` to add a row and `await formset.pop(key)` to
remove one. Each form has its own address and draft; signed membership carries
rows across requests. `validate()` uses the current child values and enforces
minimum, maximum, and cross-form rules. A subclass can declare its own save
action and emit a `Glue.event()` after a successful save.

### Editing saved records

Pass `instances` to load saved records as rows, and `initial` to add prefilled
blank rows after them:

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

`instances` requires a `ModelForm`. Each record must already be saved.

`await formset.save()` validates every row. If any row is invalid, nothing is
saved and each invalid row shows its errors. Otherwise every row is saved in one
transaction: edited records are updated and new rows are created.

Removing a row with `pop` does not delete anything by itself. When the row is a
saved record, the formset remembers it and `save()` deletes it along with saving
the rest. Reloading the page before saving brings the row back.

Removing a saved record needs `Glue.Access.DELETE` on the formset. With
`Glue.Access.CHANGE`, a user can remove rows they added but not saved records.

### New rows that belong to a record

When the rows are a record's children, a row added in the browser needs that
record's key, and the form should not let the user choose it. Pass
`new_row_defaults`:

```python
Glue.formset(
    request,
    'fights',
    FightNameForm,
    Glue.Access.DELETE,
    instances=gorilla.fights_as_red_corner.all(),
    new_row_defaults={'red_corner': gorilla.pk},
    can_delete=True,
)
```

Every new row starts with those values. Pass a related record as its primary
key.

Whether the user can change a default depends on the form:

- A model field the form does not include, or a form field with `disabled=True`,
  keeps the default. The browser cannot change it.
- A field the user can edit is prefilled with the default, and what the user
  types is saved. Use this to start every added row with a sensible value.

Keep the owning record's key off the row form, as `FightNameForm` does, so it
stays fixed.

`await formset.append(initial)` accepts initial values only for fields the form
lets a user edit. Any other key is rejected.

### Changing how rows are written

Override `save_forms` or `delete_removed` on a `Glue.FormSet` subclass to change
how rows are written, for example to save through a service or to soft-delete.
The `save_forms` below saves each row through a
[django-spire](https://django-spire.stratusadv.com) model service
([service layer guide](https://django-spire.stratusadv.com/app_guides/service/overview/));
`services.save_model_obj` is django-spire's, not Glue's:

```python
class SkillFormSet(Glue.FormSet):
    form_class = SkillForm
    can_delete = True

    def save_forms(self, form_list):
        for form in form_list:
            form.instance.services.save_model_obj(**form.cleaned_data)

    def delete_removed(self, queryset):
        queryset.update(is_deleted=True)
```

`save_forms` receives the validated Django forms of the remaining rows.
`delete_removed` receives a queryset of the removed records. Both run inside the
save transaction.

By default a saved record is only written when its row has changed. An
override of `save_forms` receives every row and decides for itself; check
`form.has_changed()` to keep that behavior.
