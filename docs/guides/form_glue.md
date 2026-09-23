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

`Glue.formset()` creates a keyed collection of form children from a form class
or `FormSetGlue` subclass. It does not wrap a Django `BaseFormSet` instance.
Each form has its own address and draft. The collection owns membership and
validates its minimum, maximum, and deletion rules.
