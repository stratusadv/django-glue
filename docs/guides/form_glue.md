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

| Form Type | Creates Proxy | Behavior |
|-----------|--------------|----------|
| **ModelForm** | `GlueModelProxy` | Acts as a model proxy with the ModelForm's validation rules |
| **Regular Form** | `GlueFormProxy` | Provides validation and cleaned data access |

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

This creates a `GlueModelProxy` — you can use `get()`, `save()`, and `delete()` just like a regular model proxy, but validation uses your custom ModelForm.

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

This creates a `GlueFormProxy` — you can use `get()`, `validate()`, and `save()`.

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

## Frontend: Using a Form Proxy

### Regular Form (GlueFormProxy)

#### Reading Field Values

The `get()` method fetches field values and populates the proxy's internal state. Field values are then accessible as properties:

```javascript
await Glue.form.contact_form.get()

// After get(), access values as properties
console.log(Glue.form.contact_form.name)
console.log(Glue.form.contact_form.email)
```

#### Setting Field Values

```javascript
Glue.form.contact_form.name = 'John Doe'
Glue.form.contact_form.email = 'john@example.com'
Glue.form.contact_form.message = 'Hello!'
Glue.form.contact_form.priority = 'high'
```

#### Validating Without Saving

```javascript
const result = await Glue.form.contact_form.validate()

if (result.success) {
    console.log('Cleaned data:', result.cleaned_data)
} else {
    console.log('Errors:', result.errors)
}
```

#### Saving

```javascript
const result = await Glue.form.contact_form.save()

if (result.success) {
    console.log('Form saved!')
    console.log('Cleaned data:', result.cleaned_data)
} else {
    console.log('Validation errors:', result.errors)
}
```

### ModelForm (GlueModelProxy)

When you pass a ModelForm to `Glue.form()`, it creates a model proxy. Use it like any model proxy:

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
console.log(nameField.label)      // "Name"
console.log(nameField.required)   // true
console.log(nameField.type)       // "CharField"
console.log(nameField.max_length) // 100
```

For foreign key fields with choices:

```javascript
const brandField = Glue.model.task_form.$fields.brand
const choices = await brandField.choices()
// Returns: [[pk, "display name"], ...]
```

## Full Example: Contact Form

### Backend

```python
from django.shortcuts import render
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

### Frontend

```html
{% load django_glue %}
<!DOCTYPE html>
<html>
<head>
    <title>Contact Us</title>
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

                <label>Email</label>
                <input x-model="Glue.form.contact_form.email" type="email">

                <label>Message</label>
                <textarea x-model="Glue.form.contact_form.message"></textarea>

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
