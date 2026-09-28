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

The collection starts empty. Call `await formset.append(initial)` to add a row
and `await formset.pop(key)` to remove one on the server. Each form has its own
address and draft; signed membership carries rows across requests. `validate()`
uses the current child values and enforces minimum, maximum, and cross-form
rules. A subclass can declare a save action and emit a `Glue.event()` after a
successful save.
