# Form Glue Guide

## Purpose

Form glue allows you to bind Django Forms (both regular Forms and ModelForms) to JavaScript with full validation support. You can set field values, validate data, and save — all from the frontend.

### When to Use

- When you need to validate form data on the server before saving.
- When you have a non-model form (e.g., a contact form) that needs server-side validation.
- When you want to use a Django ModelForm but interact with it from JavaScript.

### When Not to Use

- When you only need to display form data without editing. Pass the data in your view context instead.
- When you need direct model CRUD operations without form validation. Use [model glue](model_object_glue.md) instead.

## Important: ModelForms vs Regular Forms

The `Glue.form()` shortcut behaves differently depending on the form type:

| Form Type       | Frontend Namespace | Behavior                                              |
| --------------- | ------------------ | ----------------------------------------------------- |
| **ModelForm**   | `Glue.model`       | Acts as a model glue object with the ModelForm's validation rules |
| **Regular Form** | `Glue.form`       | Provides validation and cleaned data access           |

This means when you pass a ModelForm to `Glue.form()`, it creates a model glue object (accessible via `Glue.model`), not a form glue object. This gives you full model behavior (lazy loading, field accessors, `delete()`) with your custom ModelForm's validation.

### ModelForm Example

```python
from myapp.forms import TaskForm  # A ModelForm

task = Task.objects.get(pk=pk)
form = TaskForm(instance=task)

Glue.form(
    request=request,
    unique_name='task_form',
    target=form,
    access=GlueAccess.CHANGE,
)
```

This creates a model glue object accessible as `Glue.model.task_form`:

```javascript
// Fetch current values
await Glue.model.task_form.load()

// Modify fields
Glue.model.task_form.title = 'Updated Task'
Glue.model.task_form.done = true

// Save (uses the ModelForm for validation)
const result = await Glue.model.task_form.save()

// Delete
await Glue.model.task_form.delete()
```

### Regular Form Example

```python
from myapp.forms import ContactForm  # A regular Form

form = ContactForm()

Glue.form(
    request=request,
    unique_name='contact_form',
    target=form,
    access=GlueAccess.CHANGE,
)
```

This creates a form glue object accessible as `Glue.form.contact_form`:

```javascript
// Field values are available from form.initial
Glue.form.contact_form.name = 'John Doe'
const result = await Glue.form.contact_form.validate()
```

## Backend: Registering a Form

### With a Regular Form

```python
from django_glue import Glue, GlueAccess
from myapp.forms import ContactForm

def contact_view(request):
    form = ContactForm()

    Glue.form(
        request=request,
        unique_name='contact_form',
        target=form,
        access=GlueAccess.CHANGE,
    )

    return render(request, 'contact.html')
```

### With a ModelForm

```python
from django_glue import Glue, GlueAccess
from myapp.forms import TaskForm
from myapp.models import Task

def task_edit_view(request, pk):
    task = Task.objects.get(pk=pk)
    form = TaskForm(instance=task)

    Glue.form(
        request=request,
        unique_name='task_form',
        target=form,
        access=GlueAccess.DELETE,
    )

    return render(request, 'task_edit.html')
```

## Frontend: Using a Regular Form

### Fetching Field Values

Field values are initialized from the form's `initial` data when the glue object is created, so you can access them directly:

```javascript
// Values from form.initial are available immediately
console.log(Glue.form.contact_form.name)
console.log(Glue.form.contact_form.email)
```

The `load()` action is available and returns field definitions and initial values:

```javascript
const result = await Glue.form.contact_form.load()
// Returns: { state: {...} }
```

### Setting Field Values

```javascript
Glue.form.contact_form.name = 'John Doe'
Glue.form.contact_form.email = 'john@example.com'
Glue.form.contact_form.message = 'Hello!'
Glue.form.contact_form.priority = 'high'
```

### Validating Without Saving

```javascript
const result = await Glue.form.contact_form.validate()

if (result.valid) {
    console.log('Form is valid!')
} else {
    console.log('Errors:', result.errors)
}
```

The validation response follows this shape:

```javascript
{
    valid: true,
    errors: {}
}
```

Or on failure:

```javascript
{
    valid: false,
    errors: { email: ['Enter a valid email address.'] }
}
```

### Saving

```javascript
const result = await Glue.form.contact_form.save()

if (result.valid) {
    console.log('Form saved!')
} else {
    console.log('Validation errors:', result.errors)
}
```

The `save()` action runs validation first, then processes the cleaned data. For regular forms, the server validates and processes the data.

## Checking for Errors

Use `hasErrors()` to check for validation errors:

```javascript
// Check if any field has errors
if (Glue.form.contact_form.hasErrors()) {
    console.log('Form has errors')
}

// Check a specific field
if (Glue.form.contact_form.hasErrors('email')) {
    console.log('Email field has errors')
}
```

## Field Metadata

Access field definitions through the `$fields` property:

```javascript
const nameField = Glue.form.contact_form.$fields.name
console.log(nameField.label)       // 'Name'
console.log(nameField.required)    // true
console.log(nameField.type)        // 'CharField'
console.log(nameField.max_length)  // 100
console.log(nameField.help_text)   // null or help text string

// Field value and errors
console.log(nameField.value)       // current field value
console.log(nameField.has_errors)  // true if field has validation errors
console.log(nameField.error_text)  // error messages as string
```

### Choice Fields

For fields with choices (e.g., `ChoiceField`, `MultipleChoiceField`), the field metadata includes the available choices:

```javascript
const priorityField = Glue.form.contact_form.$fields.priority
console.log(priorityField.choices)
// [['low', 'Low'], ['medium', 'Medium'], ['high', 'High']]
```

### Foreign Key Choices

For fields that reference other models, choices are loaded lazily:

```javascript
const brandField = Glue.form.contact_form.$fields.brand
const choices = await brandField.choices()
// Returns: [{pk: 1, __str__: "Brand A"}, ...]
```

Choices are cached to avoid duplicate requests.

By default a relation field's choices load in a single request, with no
limit -- fine for a small related table, but every row goes over the wire
for a large one. A field can opt into batched, searchable loading instead by
declaring `foreign_key_choice_config` on the `ModelForm`:

```python
class ContactForm(forms.ModelForm):
    foreign_key_choice_config = {
        'company': {'search_field': 'name', 'batch_size': 50},
    }

    class Meta:
        model = Contact
        fields = ['name', 'company']
```

With that config, the field's proxy exposes:

```javascript
const companyField = Glue.form.contact_form.$fields.company

// First 50 rows, ordered by pk.
await companyField.choices
companyField.hasMoreChoices  // true if the related table has more than 50 rows

// Fetch the next 50, appended to the existing choices.
await companyField.loadMoreChoices()

// Server-side search (`name__icontains`), replacing choices with matches
// until clearSearch() runs. searchField must be passed explicitly -- there's
// no way to filter on a model's __str__ at the database layer.
await companyField.searchChoices('acme', 'name')
companyField.hasMoreChoices  // true if the search itself has more matches
await companyField.loadMoreChoices()  // continues the active search

companyField.clearSearch()  // reverts to the default (unsearched) choices
```

A field with no `foreign_key_choice_config` entry keeps returning every row
in one response, unchanged from before this existed.

## Full Example: Contact Form

### Backend

```python
# myapp/forms.py
from django import forms


class ContactForm(forms.Form):
    name = forms.CharField(max_length=100, required=True)
    email = forms.EmailField(required=True)
    message = forms.CharField(widget=forms.Textarea, required=True)
    priority = forms.ChoiceField(
        choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High')],
        required=True,
    )
```

```python
# myapp/views.py
from django.shortcuts import render
from django_glue import Glue, GlueAccess
from .forms import ContactForm

def contact_view(request):
    form = ContactForm()

    Glue.form(
        request=request,
        unique_name='contact_form',
        target=form,
        access=GlueAccess.CHANGE,
    )

    return render(request, 'contact.html')
```

### Frontend

```html
{% load django_glue %}
<!DOCTYPE html>
<html>
<head>
    <title>Contact Us</title>
    <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3/dist/cdn.min.js"></script>
</head>
<body>
    <div x-data="{
        submitted: false,
        submitting: false,
        errors: {},

        async submitForm() {
            this.submitting = true
            const result = await Glue.form.contact_form.validate()
            this.submitting = false

            if (result.valid) {
                const saveResult = await Glue.form.contact_form.save()
                if (saveResult.valid) {
                    this.submitted = true
                } else {
                    this.errors = saveResult.errors
                }
            } else {
                this.errors = result.errors
            }
        }
    }">
        <template x-if="submitted">
            <p>Thank you for your message!</p>
        </template>

        <template x-if="!submitted">
            <form @submit.prevent="submitForm()">
                <label>Name</label>
                <input x-model="Glue.form.contact_form.name" type="text">
                <template x-if="errors?.name">
                    <span class="error" x-text="errors.name[0]"></span>
                </template>

                <label>Email</label>
                <input x-model="Glue.form.contact_form.email" type="email">
                <template x-if="errors?.email">
                    <span class="error" x-text="errors.email[0]"></span>
                </template>

                <label>Message</label>
                <textarea x-model="Glue.form.contact_form.message"></textarea>
                <template x-if="errors?.message">
                    <span class="error" x-text="errors.message[0]"></span>
                </template>

                <label>Priority</label>
                <select x-model="Glue.form.contact_form.priority">
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                </select>

                <button type="submit" :disabled="submitting">Send</button>
            </form>
        </template>
    </div>

    {% django_glue_init %}
</body>
</html>
```

## Event Listeners

```javascript
Glue.form.contact_form.addListener('validate', (event) => {
    console.log('Validation result:', event.result)
}, 'after')

Glue.form.contact_form.addListener('save', (event) => {
    console.error('Save failed:', event.error)
}, 'error')
```

## Access Levels

| Access Level | Available Actions                        |
| ------------ | ---------------------------------------- |
| `VIEW`       | `load()`, `foreign_key_choices()`        |
| `CHANGE`     | All VIEW actions + `validate()`, `save()` |
