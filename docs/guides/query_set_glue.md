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

## Query permissions

By default, client filters and ordering can use exposed concrete fields and
explicitly projected related fields. The signed query capability checks the
complete field path and lookup. Exposing `project__name` permits a suitable
lookup such as `project__name__icontains`; it does not permit queries on other
fields of `project`. A relation's raw ID can be queried without exposing the
related model's other fields. Glue allows a conservative set of lookups for
each field type, such as `exact` and string `icontains`.

Use `filters=` or `ordering=` to replace either derived permission set:

```python
from django.db.models.functions import Length

Glue.queryset(
    request=request,
    target=Task.objects.annotate(title_length=Length('title')),
    unique_name='tasks',
    fields=Glue.fields('id', 'title', project=('name',)),
    filters={'project__name': ['exact', 'icontains'], 'title_length': ['gte']},
    ordering=['title', 'title_length'],
)
```

`None` derives permissions from exposed fields; an empty mapping or list
disables that operation. Explicit paths may name an unexposed field, an
annotation, a registered transform, or a reverse relation. These paths grant
query access even when row values stay hidden, so review them as data exposure.
For example, `filters={'created_at__year': ['gte']}` permits that transform,
while `filters={'name': ['regex']}` opts into a registered lookup that Glue
does not grant by default. The server validates configured paths and lookups
when creating the signed capability and again when handling a request.

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
