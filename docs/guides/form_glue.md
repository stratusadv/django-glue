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
```

The proxy exposes declared fields as editable properties. `$fields` contains
field descriptions and current validation errors. An invalid `validate()`
acknowledges the submitted draft and returns errors without turning the draft
into a server-side session object.

### Saving from the browser

A form saves through an action the application declares, such as a form
callable or a component's call, so the application's own rules run. Glue also
has a default `save()`, which validates the form and runs Django's
`ModelForm.save()`. It is offered to the browser only when the model form's
`Meta` asks for it (ADR 040):

```python
class GorillaForm(forms.ModelForm):
    class Meta:
        model = Gorilla
        fields = ['name', 'age']
        glue_default_save = True
```

```javascript
const form = Glue.form.gorilla
await form.save()
```

Without `glue_default_save = True`, the browser is not sent `save`, and a call
to it is refused as `missing_attribute`. Use the default only when
`ModelForm.save()` is the whole of what saving should do; a form whose model is
saved through a service, or that feeds a component's action, leaves it off.
The option governs only what Glue offers the browser: server code may still
call the form's own `save()`. A plain `Form` has no `save()` and never offers
one, and setting the option on it raises `ImproperlyConfigured`. A subclass
keeps the option when its `Meta` inherits the parent's, as
`class Meta(GorillaForm.Meta)`, and loses it with a fresh `class Meta`, as
Django's other `Meta` options do.

A successful default save advances the form's target identity in the successor
policy, and an invalid one returns errors as `validate()` does.

A form class can declare its own action as a Glue callable. It runs on the form
bound with the user's draft, so `self.is_valid()` validates what the user typed
and its errors reach `$fields` as `validate()`'s do. A parameter named `request`
receives the request:

```python
class SignUpForm(forms.Form):
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)

    @Glue.attr(required_access=Glue.Access.ADD)
    def submit(self, request: HttpRequest) -> Glue.Response | None:
        if not self.is_valid():
            return None
        user = create_account(self.cleaned_data['email'], self.cleaned_data['password'])
        login(request, user)
        return Glue.RedirectResponse('home:dashboard')
```

```javascript
await Glue.form.sign_up.submit()
```

`editable=` limits which declared form fields accept browser updates. Choice
fields remain scalar or flat-list values on the wire; Glue rejects nested
objects in their place. File inputs travel as multipart file parts.

A password field is write-only, as it is in a Django form. A field whose
widget is a `PasswordInput` keeps its value out of the policy token and out of
every response, so the password the user typed never comes back from the
server:

```python
class SignUpForm(forms.Form):
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)
```

The browser keeps the typed value and sends it with each call, so the field
stays filled in after `validate()` reports an error elsewhere. A call that
carries it hides its body from Django's error reports. A field that should
show its value again says so as in Django, with
`forms.PasswordInput(render_value=True)`.

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

The collection starts empty unless it is seeded. Set `extra` to start with
blank rows, after any it was seeded with:

```python
class InvoiceLineFormSet(Glue.FormSet):
    form_class = InvoiceLineForm
    min_num = 1
    extra = 1
```

`extra` defaults to 0 and can also be passed to the constructor or to
`Glue.formset()`. Unlike a Django formset, an extra row is validated like any
other: one the user never touched must be filled in or removed.

Call
`await formset.append(initial)` to add a row and `await formset.pop(key)` to
remove one. Each form has its own address and draft; signed membership carries
rows across requests. `validate()` uses the current child values and enforces
minimum, maximum, and cross-form rules. A subclass can declare its own save
action and emit a `Glue.event()` after a successful save.

In Python, a Glue form and a Glue formset answer as Django's do. `is_valid()`
validates as `validate()` does and returns a boolean, and `cleaned_data` is the
form's dict, or for a formset one dict per row. Reading a form's `cleaned_data`
before it is validated raises `AttributeError`. A component uses them to
[save several forms in one call](components.md#save-several-forms-in-one-call).

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
transaction: edited records are updated and new rows are created. A formset
offers `save()` to the browser only when its row form's `Meta` sets
`glue_default_save = True`, as a single form does; without it, save the rows
from a component's call.

Removing a row with `pop` does not delete anything by itself. When the row is a
saved record, the formset remembers it and `save()` deletes it along with saving
the rest. Reloading the page before saving brings the row back.

Removing a saved record needs `Glue.Access.DELETE` on the formset. With less, a
user can remove rows they added but not saved records.

A formset that only creates rows needs `Glue.Access.ADD`: that is enough to add
rows, remove them, validate and save. Once the formset holds a saved record,
validating and saving need `Glue.Access.CHANGE`.

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

### Rows that need constructor arguments

A row form that needs to know something to build its fields, such as the
company whose accounts it may choose from, takes it as a constructor argument.
Pass it in `form_kwargs`, as with a Django formset:

```python
class JournalLineForm(forms.ModelForm):
    class Meta:
        model = JournalLine
        fields = ('account', 'value')

    def __init__(self, *args, company_id: int, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fields['account'].queryset = Account.objects.filter(company_id=company_id)


JournalLineFormSet(access=Glue.Access.ADD, form_kwargs={'company_id': company.pk})
```

Every row is built with them, including rows added in the browser and rows
rebuilt on a later request. They are signed into the token, so pass plain values,
and a related record as its key.

To give every row something the formset loads once per request, such as the rows
each form looks its choice up in, override `get_form_kwargs()` and add to what it
returns. A row rebuilt on its own, for a call of its own such as loading its
choices, gets only `form_kwargs`, so its form must also work without the added
values (ADR 041).

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
