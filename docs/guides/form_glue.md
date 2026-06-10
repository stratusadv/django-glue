# Form Proxy Guide

## Purpose

Form proxies allow you to bind Django Forms (both regular Forms and ModelForms) to JavaScript with full validation support. You can set field values, validate data, and save — all from the frontend.

### When to Use

- When you need to validate form data on the server before saving.
- When you have a non-model form (e.g., a contact form) that needs server-side validation.
- When you want to use a Django ModelForm but interact with it from JavaScript.

### When Not to Use

- When you only need to display form data without editing. Pass the data in your view context instead.
- When you need direct model CRUD operations without form validation. Use a [Model proxy](model_object_glue.md) instead.

## Important: ModelForms vs Regular Forms

The `Glue.form()` shortcut behaves differently depending on the form type:

| Form Type | Creates Proxy | Frontend Namespace | Behavior |
|-----------|--------------|-------------------|----------|
| **ModelForm** | `GlueModelProxy` | `Glue.model` | Acts as a model proxy with the ModelForm's validation rules |
| **Regular Form** | `GlueFormProxy` | `Glue.form` | Provides validation and cleaned data access |

This means when you pass a ModelForm to `Glue.form()`, it creates a model proxy (accessible via `Glue.model`), not a form proxy. This gives you full model proxy behavior (lazy loading, field accessors, `delete()`) with your custom ModelForm's validation.

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

This creates a `GlueModelProxy` accessible as `Glue.model.task_form`:

```javascript
// Fetch current values
await Glue.model.task_form.get()

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

This creates a `GlueFormProxy` accessible as `Glue.form.contact_form`:

```javascript
// Field values are available from form.initial
Glue.form.contact_form.name = 'John Doe'
const result = await Glue.form.contact_form.validate()
```

## Backend: Registering a Form Proxy

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

## Frontend: Using a Regular Form Proxy

### Fetching Field Values

Field values are initialized from the form's `initial` data when the proxy is created, so you can access them directly:

```javascript
// Values from form.initial are available immediately
console.log(Glue.form.contact_form.name)
console.log(Glue.form.contact_form.email)
```

The `get()` action is available and returns field definitions and initial values:

```javascript
const result = await Glue.form.contact_form.get()
// Returns: { fields: {...}, values: {...}, errors: {} }
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

if (result.success) {
    console.log('Cleaned data:', result.cleaned_data)
} else {
    console.log('Errors:', result.errors)
}
```

The validation response follows this shape:

```javascript
{
    success: true,
    errors: null,
    cleaned_data: { name: 'John Doe', email: 'john@example.com', ... }
}
```

Or on failure:

```javascript
{
    success: false,
    errors: { email: ['Enter a valid email address.'] },
    cleaned_data: {}
}
```

### Saving

```javascript
const result = await Glue.form.contact_form.save()

if (result.success) {
    console.log('Form saved!')
    console.log('Cleaned data:', result.cleaned_data)
} else {
    console.log('Validation errors:', result.errors)
}
```

The `save()` action runs validation first, then processes the cleaned data. For regular forms, the server returns the cleaned data in the response.

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
// Returns: [[pk, "display name"], ...]
```

Choices are cached across all proxy instances to avoid duplicate requests.

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

            if (result.success) {
                const saveResult = await Glue.form.contact_form.save()
                if (saveResult.success) {
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

| Access Level | Available Actions |
|-------------|-------------------|
| `VIEW` | `get()`, `foreign_key_choices()` |
| `CHANGE` | All VIEW actions + `validate()`, `save()` |
