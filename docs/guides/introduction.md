# Core concepts

## Register an object

A Django view registers a configured Glue object with a unique page name:

```python
from django_glue import Glue


def task_page(request):
    Glue.model(
        request=request,
        target=task,
        unique_name='task',
        access=Glue.Access.CHANGE,
        fields=['id', 'title', 'done'],
    )
    return render(request, 'tasks/detail.html')
```

`{% django_glue_init %}` sends the page's addressed objects to the browser.
The client exposes named roots under `Glue.model`, `Glue.querySet`,
`Glue.form`, and `Glue.function`. A `Glue.Component` is mounted through
`{% glue_component %}` and is addressed by its rendered root.

## Work with a proxy

```javascript
const task = Glue.model.task
task.title = 'Prepare report'
await task.save()

const rows = await Glue.querySet.tasks.filter({done: false}).all()
for (const row of rows.items) console.log(row.title)
```

An address identifies one live proxy. A model's projected relation is a
separate addressed child; its raw foreign-key value remains a field on the
model. Queryset rows and component children also have their own addresses.

## State and calls

The signed policy token holds authority, reconstruction parameters, retained
state, and shallow child addresses. Stable field and callable descriptions
arrive in `static_data`; derived output and validation errors arrive in
`computed_data`. The browser sends only the difference between its editable
draft and the last acknowledged state. The server admits those updates,
runs the call, and returns the successor snapshot.

Every object arrives complete when introduced. Queryset rows arrive in answer
to a query. Call `$refresh()` to re-derive an object's server output.

## Access and lifecycle

`VIEW < ADD < CHANGE < DELETE` is the access cascade. `ADD` can create an
unsaved draft without granting edits to persisted rows. The server checks
authorization at introduction, reconstruction, and invocation.

Removing a child or collection item disposes its proxy. Existing references
then reject calls; reintroducing the same address creates a new proxy.

Continue with the [model](model_object_glue.md),
[queryset](query_set_glue.md), [form](form_glue.md), or
[component](components.md) guide.
