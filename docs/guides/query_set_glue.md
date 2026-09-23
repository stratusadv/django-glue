# Querysets

`Glue.queryset()` registers a configured Django queryset. Its introduction
contains the query capability and interface; rows arrive when the client
queries it.

```python
Glue.queryset(
    request=request,
    target=Task.objects.filter(team=request.user.team),
    unique_name='tasks',
    access=Glue.Access.CHANGE,
    fields=['id', 'title', 'done'],
    editable=['title', 'done'],
    batch_size=50,
)
```

The server reconstructs rows through the signed queryset, preserving the
query's authorization and filters. Every row is its own addressed model proxy.

```javascript
const tasks = Glue.querySet.tasks
await tasks.all()
for (const task of tasks.items) console.log(task.title)

const open = await tasks.filter({done: false}).orderBy('title').all()
console.log(open.items)

if (open.hasNext) await open.loadMore()
```

`filter()`, `orderBy()`, and `slice(start, stop)` create query views. `all()`
fetches a batch, `loadMore()` follows the signed continuation, and `count()`
queries a total separately. `all({withTotal: true})` includes a total in its
first result. `refresh()` or `$refresh()` re-runs the relevant query.

`get(pk)` returns a configured row by identity. `new(initial)` creates an
unsaved row draft from admitted editable values. On an `ADD` queryset,
existing rows are `VIEW`, while a new draft can be saved once. With `CHANGE`
or `DELETE`, saved rows receive the corresponding access.

Nested `fields` paths project addressed relation children, and `choices=`
configures relation choice sources. `editable=` narrows the write projection
for each row. `select_related()` and `prefetch_related()` optimize ORM queries
but do not expose additional fields.

For a projected reverse or many-to-many relation, the child is also a
queryset. Its signed continuation binds it to the owning relation. A draft
created through that child attaches through the relation when saved.
