# Glue API

Import `Glue` from `django_glue`. Each registration shortcut takes the current
request and creates an addressed root for that page.

| Method | Registers |
| --- | --- |
| `Glue.model()` | One configured Django model |
| `Glue.queryset()` | A queryset whose rows are addressed model objects |
| `Glue.form()` | A Django form or model form |
| `Glue.formset()` | A keyed collection of forms |
| `Glue.function()` | An authorized Python function |
| `Glue.object()` | A configured custom `BaseGlue` instance |

`Glue.Component` classes are discovered at startup and mounted with
`{% glue_component %}` in a Django template.

## Model projections and choices

`fields` and `exclude` select exposed model fields. Dotted `__` paths traverse
relations and create separate addressed children. A relation's raw identity
value stays on the owner:

```python
Glue.model(
    request=request,
    target=entry,
    unique_name='entry',
    access=Glue.Access.CHANGE,
    fields=['id', 'hours', 'project', 'project__name'],
    choices={
        'project': Glue.choices(
            Project.objects.filter(active=True),
            search_fields=['name'],
        ),
    },
)
```

`Glue.fields(*paths, **relations)` produces the same canonical path selection
as a list of `__` paths. `editable=` narrows fields that accept browser edits;
it does not expand read exposure or access level. `Glue.choices()` configures
trusted relation choice sources. A searchable source returns bounded matches
for a query; an implicit choice list has a small default cap and raises a
configuration error if the related table exceeds it.

## Access

`Glue.Access.VIEW`, `ADD`, `CHANGE`, and `DELETE` form an increasing cascade.
An `ADD` queryset can create a draft through `new(initial)` while its saved
rows remain read-only. An unsaved draft needs `ADD` to save; a persisted model
needs `CHANGE`.

## First snapshot and refresh

Every introduced object has its complete first state and derived output.
Queryset rows arrive on query calls. `$refresh()` asks the server to re-derive
an object's output.

## Source

::: django_glue.Glue
