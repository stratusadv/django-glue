# renderInnerHtml Guide

## Purpose

`renderInnerHtml` is the most common GlueView method — it replaces the contents of a DOM element with HTML rendered by a Django view, while preserving the container element itself.

### When to Use

- When you want to update a section of a page without replacing the container element.
- When the container element has event handlers or Alpine.js bindings you want to preserve.

### When Not to Use

- When you need to replace the container element itself. Use `renderOuterHtml` instead.
- When you need to insert content without removing existing content. Use `renderInsertAdjacentHtml*` methods.

## How It Works

```javascript
await view.renderInnerHtml(targetElement, payload)
```

The target element's `innerHTML` is replaced with the rendered HTML from the Django view. Any proxies registered by that view are automatically initialized.

## Example: Dynamic Dashboard Content

### Backend

```python
from django.template.response import TemplateResponse
from django_glue import Glue, GlueAccess
from myapp.models import Task

def dashboard_content_view(request):
    """Renders dashboard content based on selected task."""
    body = json.loads(request.body) if request.body else {}
    task_id = body.get('view_payload', {}).get('taskId')

    if task_id:
        task = Task.objects.get(pk=task_id)
        Glue.model(
            request=request,
            unique_name='dashboard_task',
            target=task,
            access=GlueAccess.CHANGE,
        )

    return TemplateResponse(request, 'tasks/_dashboard_content.html', {'taskId': task_id})
```

### Frontend

```html
<div x-data="{
    selectedTaskId: 1,
    async reloadContent() {
        const view = Glue.view('/dashboard/content/')
        await view.renderInnerHtml(
            document.getElementById('dashboard-content'),
            { taskId: this.selectedTaskId }
        )
    }
}" x-init="reloadContent()">
    <select x-model.number="selectedTaskId" @change="reloadContent()">
        <option value="1">Task 1</option>
        <option value="2">Task 2</option>
        <option value="3">Task 3</option>
    </select>

    <div id="dashboard-content">
        <!-- Content will be loaded here -->
    </div>
</div>
```

## renderInnerHtml vs renderOuterHtml

| Method | Behavior | Use When |
|--------|----------|----------|
| `renderInnerHtml` | Replaces element's **contents** | Container element has bindings you need to keep |
| `renderOuterHtml` | Replaces the **element entirely** | You want the response HTML to define the container |

## See Also

For a complete overview of all GlueView methods, see the [GlueView Guide](view_glue.md).
