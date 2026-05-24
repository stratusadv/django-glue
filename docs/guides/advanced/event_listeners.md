# Event Listeners

## Overview

Every JavaScript proxy supports an event listener system that lets you react to actions before they execute, after they succeed, or when they fail. This is useful for showing loading states, handling errors, or triggering side effects.

## Event Types

Each action supports three event types:

| Type | When It Fires | Event Object Contains |
|------|--------------|----------------------|
| `'before'` | Before the HTTP request is sent | `action`, `proxy`, `payload` |
| `'after'` | After a successful response | `action`, `proxy`, `result` |
| `'error'` | When the request fails | `action`, `proxy`, `error` |

## Adding Listeners

Use `addListener(actionName, callback, type)`:

```javascript
Glue.model.task.addListener('save', (event) => {
    console.log('About to save:', event.payload)
}, 'before')

Glue.model.task.addListener('save', (event) => {
    console.log('Saved successfully:', event.result)
}, 'after')

Glue.model.task.addListener('save', (event) => {
    console.error('Save failed:', event.error)
}, 'error')
```

The default event type is `'after'`, so you can omit it:

```javascript
Glue.model.task.addListener('save', (event) => {
    console.log('Result:', event.result)
})
```

## Chaining

`addListener` returns the proxy instance, so you can chain multiple listeners:

```javascript
Glue.model.task
    .addListener('save', showLoading, 'before')
    .addListener('save', hideLoading, 'after')
    .addListener('save', showError, 'error')
    .addListener('delete', onDeleted, 'after')
```

## Removing Listeners

Remove a specific listener:

```javascript
const onSave = (event) => { /* ... */ }

Glue.model.task.addListener('save', onSave, 'after')
// Later...
Glue.model.task.removeListener('save', onSave, 'after')
```

Clear all listeners on a proxy:

```javascript
Glue.model.task.clearListeners()
```

## Practical Example: Loading State

```html
<div x-data="{
    saving: false,
    saveError: null,

    async saveTask() {
        this.saving = true
        this.saveError = null

        try {
            const result = await Glue.model.task.save()
            if (result.success) {
                alert('Saved!')
            }
        } catch (error) {
            this.saveError = error.message
        } finally {
            this.saving = false
        }
    }
}">
    <input x-model="Glue.model.task.title">
    <button @click="saveTask()" :disabled="saving">
        <span x-text="saving ? 'Saving...' : 'Save'"></span>
    </button>
    <template x-if="saveError">
        <p class="error" x-text="saveError"></p>
    </template>
</div>
```

## Practical Example: Toast Notifications

```javascript
// Register a global notification handler
function showToast(message, type = 'info') {
    // Your toast implementation
    console.log(`[${type}] ${message}`)
}

Glue.model.task
    .addListener('save', (event) => {
        showToast('Saving task...', 'info')
    }, 'before')
    .addListener('save', (event) => {
        showToast('Task saved successfully', 'success')
    }, 'after')
    .addListener('save', (event) => {
        showToast('Failed to save task', 'error')
    }, 'error')
```

## QuerySet Event Bubbling

Events from child model proxies automatically bubble up to the parent queryset's listeners:

```javascript
// Listen for any save on any item in the queryset
Glue.querySet.tasks.addListener('save', (event) => {
    console.log('An item was saved')
}, 'after')

// Listen for any delete
Glue.querySet.tasks.addListener('delete', (event) => {
    console.log('An item was deleted')
}, 'after')
```

This means you can attach a single listener to the queryset to track all CRUD operations on its items, without having to attach listeners to each individual model proxy.

## Available Actions

You can attach listeners to any action that the proxy supports:

| Proxy | Actions You Can Listen To |
|-------|--------------------------|
| Model Proxy | `get`, `save`, `delete`, `validate`, `foreign_key_choices` |
| QuerySet Proxy | `query_with_params`, `save`, `delete`, `get`, `new`, `foreign_key_choices` |
| Form Proxy | `get`, `save`, `validate`, `foreign_key_choices` |
