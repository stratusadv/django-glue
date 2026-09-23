# `renderInnerHtml`

`renderInnerHtml(target, payload)` replaces a target's contents with HTML
from an ordinary Django view while retaining the target element:

```javascript
const view = Glue.view('/dashboard/content/')
await view.renderInnerHtml(document.getElementById('dashboard-content'), {
    taskId: selectedTaskId,
})
```

Render methods send a JSON POST to the target URL. The Django view reads the
payload from `request.body`:

```python
import json

from django.shortcuts import render
from django_glue import Glue


def dashboard_content_view(request):
    payload = json.loads(request.body or '{}')
    task = Task.objects.get(pk=payload['taskId'])
    Glue.model(
        request=request,
        target=task,
        unique_name='dashboard_task',
        access=Glue.Access.VIEW,
        fields=['id', 'title'],
    )
    return render(request, 'tasks/_dashboard_content.html', {'task': task})
```

The response's objects are registered before Alpine morphs the target's
children. `renderInnerHtml` accepts multiple roots or empty HTML. Use
`renderOuterHtml` when the response should replace the target itself; that
method requires one root element.

See [rendering a Django view](view_glue.md) for the other methods.
