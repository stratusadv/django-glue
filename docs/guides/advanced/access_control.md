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
required access, and `is_authorized()` can deny an object for the current request.
The server intersects the current declaration, signed capability, and current
authorization at introduction, reconstruction, and invocation. Denying one
address in a batch leaves other addresses able to advance.

## When access changes during a session

A token keeps what it granted until it expires. A `Glue.model()`,
`Glue.form()`, `Glue.queryset()` or `Glue.formset()` object is authorized when
the page that issues it loads, so on a page already open:

- **A row that leaves its queryset stays reachable.** A task reassigned away
  from "my tasks" can still be edited or deleted through the row token the
  page holds. New queries and `get(pk)` go through the queryset and no longer
  return it.
- **A revoked permission does not reach the page.** A user who loses
  `change_task` can still save through objects issued before the change.

Both last at most `DJANGO_GLUE_PROXY_POLICY_MAX_AGE_SECONDS`, 24 hours by
default. Logging out, logging in again and changing the password end every
token the session holds at once.

Where revocation must take effect immediately:

- **Make the object a component** and check current permissions and ownership
  in its `is_authorized()`, which runs on every call.
- **Add a `process_glue_call` hook** that rechecks the user's permissions on
  every call. It covers every Glue object, and a row's address carries its key,
  as in `list[42]`, when the rule needs the row.
- **Shorten the token lifetime** for the whole project with
  `DJANGO_GLUE_PROXY_POLICY_MAX_AGE_SECONDS`.

## Guarding calls with middleware

A URL guard, such as a view decorator or a middleware's `process_view`, runs
when a page loads. Later calls go to Glue's own endpoint, so a rule that reads
the URL needs a second hook to reach them: `process_glue_call`.

Every policy token records the path of the page or `Glue.view` fragment that
issued its object, its origin. A middleware in `MIDDLEWARE` that defines
`process_glue_call(request, glue_call)` runs for every object in a call, before
the object is rebuilt, with that origin resolved:

```python
from django.core.exceptions import PermissionDenied
from django.http import Http404

from django_glue.middleware import GlueMiddlewareMixin


class CompanyMiddleware(GlueMiddlewareMixin):
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        company_uuid = view_kwargs.pop('company_uuid', None)
        if company_uuid is not None and not company_context_resolve(request, company_uuid):
            raise Http404

    def process_glue_call(self, request, glue_call):
        company_uuid = glue_call.origin.kwargs.get('company_uuid')
        if company_uuid is not None and not company_context_resolve(request, company_uuid):
            raise Http404
```

`glue_call` carries:

| Field | Value |
| --- | --- |
| `origin` | The `ResolverMatch` of the path that issued the object |
| `address` | The object's address |
| `namespace` | The object's Glue family, such as `component` or `model` |
| `kind` | `call`, `update` or `refresh` |
| `attribute` | The attribute called, or `None` |

Return `None` to continue. Raise `PermissionDenied` or `Http404` to refuse the
object; it fails with `not_authorized` and the other objects in the call go
ahead. A hook can refuse but never grant: the object's own `is_authorized()`
still runs after it.

- **Every Glue object is covered**, including `Glue.model()`, `Glue.form()` and
  `Glue.queryset()` objects, whose `is_authorized()` a project cannot override.
- **Context a hook sets on the request**, such as `request.company`, is in
  place when the object is rebuilt and when its `is_authorized()` runs. Set or
  clear it for every object, so one object's context does not reach the next.
- **Glue builds its own instance of the middleware**, so the hook must not rely
  on state Django's instance set up.
- **Memoize per request, never across requests.** A membership looked up once
  per request keeps a call to many objects at one query, and stays current.
- **The origin is fixed when the object is issued.** Objects introduced during
  a call keep the origin of the object that introduced them. When a hook is
  installed, an origin that no longer resolves, after a route is removed or
  renamed, is refused.
