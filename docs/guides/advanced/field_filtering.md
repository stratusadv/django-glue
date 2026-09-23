# Field projection

Use `fields` to expose an explicit set of model fields, or `exclude` to
remove fields from the default selection. `editable` narrows the exposed
fields that accept browser updates:

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

The same projection applies to rows returned by `Glue.queryset()`. Nested
`__` paths explicitly traverse relations. A to-one traversal produces an
addressed model child; a to-many or reverse traversal produces an addressed
queryset child. `fields='__all__'` exposes ordinary fields but does not
automatically traverse relations. ORM `select_related()` and
`prefetch_related()` optimize fetching without changing exposure.

`Glue.fields()` is optional shorthand for a canonical path tuple:

```python
selection = Glue.fields('id', 'title', project=['id', 'name'])
```

That selection has the same meaning as
`['id', 'title', 'project__id', 'project__name']`.
Use `choices={'project': Glue.choices(...)}` for a separate trusted relation
choice source. A choice source does not widen the projected relation fields.
