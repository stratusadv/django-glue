# Access control

Every addressed Glue object has a signed access level:

| Level | Allows |
| --- | --- |
| `VIEW` | Read and permitted read actions |
| `ADD` | `VIEW` plus creation of an unsaved draft |
| `CHANGE` | `ADD` plus edits to a persisted target |
| `DELETE` | `CHANGE` plus deletion |

Choose the minimum level at registration:

```python
Glue.queryset(
    request=request,
    target=Task.objects.filter(team=request.user.team),
    unique_name='tasks',
    access=Glue.Access.ADD,
    fields=['id', 'title'],
    editable=['title'],
)
```

Here existing rows are `VIEW`; `new(initial)` creates an `ADD` draft that can
be saved once. After creation it becomes `VIEW`. Use `CHANGE` if saved rows
must stay editable.

Access is only one boundary. `fields` determines readable projection,
`editable` narrows writable fields, callable declarations set their own
required access, and `authorize()` can deny an object for the current request.
The server intersects the current declaration, signed capability, and current
authorization at introduction, reconstruction, and invocation. Denying one
address in a batch leaves other addresses able to advance.
