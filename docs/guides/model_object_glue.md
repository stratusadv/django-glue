# Model objects

Use `Glue.model()` for one configured Django model. Expose only the fields
the page needs:

```python
Glue.model(
    request=request,
    target=task,
    unique_name='task',
    access=Glue.Access.CHANGE,
    fields=['id', 'title', 'done', 'project', 'project__name'],
    editable=['title', 'done', 'project'],
)
```

`fields` selects readable fields. `exclude` removes fields from that
selection. `editable` narrows which exposed fields may be updated from the
browser. Access also limits writes; exposing a field does not grant permission
to edit it.

```javascript
const task = Glue.model.task
console.log(task.title)
task.title = 'Revised title'
await task.save()
```

The proxy keeps local editable changes until a response acknowledges them.
`task.$fields.title` describes the field and carries validation errors. A
failed save may return errors while preserving the draft. `$refresh()` asks
the server to re-derive output without discarding edits made during the
request.

## Relations

`project` exposes the raw foreign-key identity through
`task.$fields.project.value`. `project__name` also projects a separate
addressed child, available as `task.project`. `fields='__all__`,
`select_related()`, and `prefetch_related()` do
not themselves expose relation traversal. Reverse and many-to-many projections
create queryset children with the usual query methods.

Use `choices=` to provide a trusted relation choice source:

```python
Glue.model(
    request=request,
    target=task,
    unique_name='task',
    access=Glue.Access.CHANGE,
    fields=['id', 'project', 'project__name'],
    choices={
        'project': Glue.choices(
            Project.objects.filter(is_active=True),
            search_fields=['name'],
        ),
    },
)
```

An implicit source uses the related model's string label and has a small
default cap. Configure a searchable source for a larger table.

## Creation and deletion

An unsaved model is an `ADD` draft. Its first save needs `ADD`; later saves
need `CHANGE`. An `ADD`-only result becomes `VIEW` after creation. `delete()`
requires `DELETE` and disposes the proxy once the server confirms removal.
Held references then reject calls.

Model objects can use `form=` or `forms=` for configured Django form
validation. The signed policy and current authorization still determine the
admitted operation.
