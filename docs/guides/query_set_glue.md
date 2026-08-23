# QuerySet Glue Guide

## Purpose

QuerySet glue allows you to work with collections of Django model instances from JavaScript. Each item returned from a queryset is a full model glue object with its own `save()` and `delete()` methods.

### When to Use

- When you need to display and edit a list of model instances.
- When you need to filter, order, or paginate data from the frontend.
- When items in a collection need their own CRUD operations.

### When Not to Use

- When you only need to display a static list. Use regular Django template context instead.
- When you only need one instance. Use [model glue](model_object_glue.md) instead.

## Backend: Registering a QuerySet

Use `Glue.queryset()` in your Django view:

```python
from django_glue import Glue, GlueAccess
from myapp.models import Task

def task_list_view(request):
    Glue.queryset(
        request=request,
        unique_name='tasks',
        target=Task.objects.all(),
        access=GlueAccess.CHANGE,
        exclude=['internal_notes'],
    )

    return render(request, 'task_list.html')
```

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `request` | `HttpRequest` | Yes | The current request |
| `unique_name` | `str` | Yes | Unique identifier for this glue object |
| `target` | `QuerySet` | Yes | The queryset to expose |
| `access` | `GlueAccess` | No | Access level (default: `VIEW`) |
| `fields` | `Sequence[str]` | Yes* | Fields to include. Use `ALL_FIELDS` for all fields |
| `exclude` | `Sequence[str]` | Yes* | Fields to exclude |
| `form` | `ModelForm` | No | Default ModelForm for validation on child items (class or instance) |
| `forms` | `Mapping[str, ModelForm]` | No | Named ModelForms for child items (classes or instances) |
| `computed_attributes` | `Mapping[str, ComputedAttribute]` | No | Readonly computed values for each item |
| `related_field_config` | `Mapping[str, dict]` | No | Field configuration for related objects (see [Model Glue: Related Field Config](model_object_glue.md#related-field-configuration)) |
| `loading_strategy` | `LoadingStrategy` | No | `LAZY` (default), `EAGER`, or `INHERIT`. See [Loading Strategy](../api/glue/shortcuts.md#loading-strategy) |
| `page_size` | `int \| None` | No | Rows per page. Defaults to the `DJANGO_GLUE_QUERYSET_PAGE_SIZE` setting (100). `None` disables paging for this queryset |

*Either `fields` or `exclude` must be provided.

!!! tip

    You can pass either a form class or a form instance for `form` and `forms`. When you pass a class, an instance is created automatically. See the [Model Glue Guide](model_object_glue.md#custom-forms) for details.

### Pagination

Every queryset is paged on the server. A query returns one page of rows plus the total count, so a table with 100,000 rows never reaches the browser in one response, whatever the frontend asks for.

```python
Glue.queryset(
    request=request,
    unique_name='tasks',
    target=Task.objects.all(),
    access=GlueAccess.VIEW,
    fields=['id', 'title'],
    page_size=25,
)
```

The default page size comes from the `DJANGO_GLUE_QUERYSET_PAGE_SIZE` setting (100). Pass `page_size=None` to send the whole queryset in one page, for small lookup tables where paging is noise.

The page size is signed into the policy token with the queryset, so the frontend can choose which page it wants but not how large a page is. Unordered querysets are ordered by `pk` before slicing so that pages do not overlap or skip rows between requests.

### Using select_related and prefetch_related

For related model fields, use `select_related` (for ForeignKey) or `prefetch_related` (for ManyToMany) on your queryset. The glue object will automatically serialize the related fields:

```python
Glue.queryset(
    request=request,
    unique_name='tasks',
    target=Task.objects.select_related('assigned_to').prefetch_related('tags'),
    access=GlueAccess.CHANGE,
    fields=['id', 'title', 'assigned_to', 'tags'],
)
```

On the frontend, related objects are nested:

```javascript
const tasks = await Glue.querySet.tasks.all()
console.log(tasks.items[0].assigned_to.name)  // Nested FK object
console.log(tasks.items[0].tags)              // M2M as array of PKs
```

### Adding Computed Attributes

Use `computed_attributes` when each returned item needs extra frontend data that is calculated in Python after the queryset is loaded.

```python
from django_glue import Glue, GlueAccess
from myapp.models import Group
from myapp.permissions import generate_group_perm_data

def group_list_view(request):
    Glue.queryset(
        request=request,
        unique_name='groups',
        target=Group.objects.prefetch_related('permissions').order_by('name'),
        access=GlueAccess.VIEW,
        fields='__all__',
        computed_attributes={
            'permission_data': generate_group_perm_data,
        },
    )

    return render(request, 'groups/list.html')
```

The callable receives the model instance and its return value is exposed as a readonly attribute on each frontend item:

```javascript
const groups = await Glue.querySet.groups.all()
console.log(groups.items[0].permission_data)
```

Computed attributes also support keyword arguments by passing a `(callable, kwargs)` tuple:

```python
Glue.queryset(
    request=request,
    unique_name='groups',
    target=Group.objects.all(),
    access=GlueAccess.VIEW,
    fields='__all__',
    computed_attributes={
        'permission_data': (generate_group_perm_data, {'with_special_role': True}),
    },
)
```

!!! note

    Computed attributes are not Django ORM annotations. They are evaluated after the queryset rows are loaded, so they cannot be used for queryset filtering or ordering. Use Django's `QuerySet.annotate()` on the queryset itself when you need database-level annotations.

## Frontend: Using the QuerySet

### Loading Items

`all()` loads the first page and resolves to the queryset itself. `items` is the loaded page as an array.

```javascript
const tasks = await Glue.querySet.tasks.all()

for (const task of tasks.items) {
    console.log(task.title)
}
```

Iterating a queryset that has not been loaded yet starts the load, so an Alpine `x-for` over `Glue.querySet.tasks.items` renders empty first and fills in when the page arrives. `loading` is `true` while a request is in flight.

Each item is a full model glue object with its own methods:

```javascript
const tasks = await Glue.querySet.tasks.all()

tasks.items[0].title = 'Updated Title'
await tasks.items[0].save()

await tasks.items[1].delete()
```

### Filtering, Ordering, and Slicing

`filter()`, `orderBy()`, and `slice()` return a new queryset proxy with the merged parameters. Nothing is fetched until that proxy is loaded or iterated.

```javascript
const active = Glue.querySet.tasks.filter({done: false})
const urgent = Glue.querySet.tasks.filter({done: false, priority: 2})
const matching = Glue.querySet.tasks.filter({title__icontains: 'search term'})

const newest = Glue.querySet.tasks.orderBy(['-created_at', 'title'])

const window = Glue.querySet.tasks.slice(0, 500)
```

Filters use Django ORM lookups and are validated on the server against the fields you exposed. `slice()` narrows the queryset itself, like `queryset[start:stop]`; the result is then paged like any other query.

The methods chain, and the same parameters always give back the same proxy object, whichever order they were chained in:

```javascript
const results = await Glue.querySet.tasks
    .filter({done: false, title__icontains: 'urgent'})
    .orderBy('-created_at')
    .all()
```

### Paging

A query loads one page. `page(n)`, `next()`, and `previous()` chain the same way `filter()` does and return the proxy for that page. `filter()`, `orderBy()`, and `slice()` always start at the first page.

```javascript
const first = await Glue.querySet.tasks.filter({done: false}).all()

first.count        // rows matching the filter on the server, across every page
first.items.length // rows on this page
first.pageNumber   // 1
first.pageSize     // 100, or null when the queryset is not paged
first.pageCount    // Math.max(1, Math.ceil(count / pageSize))
first.hasNext
first.hasPrevious

const second = await first.next().all()
const last = await first.page(first.pageCount).all()
```

`page(1)` is the base query, so `first.next().previous()` is `first`. A page past the end loads as empty with the same `count` and `pageCount`.

A chained proxy starts out showing its source's rows, `count`, and `pageCount` until its own page arrives, so an `x-for` bound to `tasks.page(page)` swaps rows in place instead of collapsing to nothing between pages.

### Infinite Scroll

`loadMore()` fetches the next page and appends it to the same proxy. `items` grows, `pageNumber` is the last page loaded, and `hasNext` says whether another page exists. Calls while a request is in flight or when there is no next page do nothing.

```javascript
const tasks = await Glue.querySet.tasks.filter({done: false}).all()

await tasks.loadMore()
tasks.items.length // two pages
```

### Select Fields

A select over a large table sends one query per keystroke and appends pages as the list is scrolled. The sentinel at the bottom of the list calls `loadMore()` whenever it comes into view (Alpine's Intersect plugin):

```html
<div x-data="{
    search: '',
    open: false,
    selected: null,
    get options() {
        return Glue.querySet.tasks.filter({title__icontains: this.search})
    },
}" @click.outside="open = false">
    <input x-model.debounce.300ms="search" @focus="open = true" placeholder="Search tasks">

    <div x-show="open" style="max-height: 16rem; overflow-y: auto">
        <template x-for="task in options.items" :key="task.$key">
            <button type="button" @click="selected = task; search = task.title; open = false" x-text="task.title"></button>
        </template>

        <div x-intersect:enter="options.loadMore()">
            <span x-show="options.loading">Loading...</span>
            <span x-show="!options.loading && options.hasNext"
                  x-text="`${options.items.length} of ${options.count}`"></span>
        </div>
    </div>
</div>
```

Changing the search text gives a different proxy, so each search term keeps its own loaded pages.

### Fetching One Item

```javascript
const task = await Glue.querySet.tasks.get(42)
```

`get(pk)` loads a single row through the queryset, so it only finds rows the queryset contains.

### Creating a New Item

```javascript
const task = await Glue.querySet.tasks.new({title: 'New Task'})
await task.save()
```

`new()` returns an unsaved model glue object with the server's defaults applied. It is not part of the loaded page until the page is reloaded.

## Methods and Properties

| Method/Property | Description |
|-----------------|-------------|
| `all()` | Load the current page; resolves to the queryset |
| `get(pk)` | Load one row by primary key |
| `new(initial)` | Build an unsaved item with default values |
| `filter(params)` | Chain: add filter lookups, reset to page 1 |
| `orderBy(fields)` | Chain: set ordering, reset to page 1 |
| `slice(start, stop)` | Chain: narrow the queryset, reset to page 1 |
| `page(number)` | Chain: select a page |
| `next()` / `previous()` | Chain: select the adjacent page |
| `loadMore()` | Append the next page to this proxy; resolves to the queryset |
| `refresh()` | Mark the whole chain stale and reload this proxy |
| `items` | Loaded rows as an array; iterating an unloaded queryset starts the load |
| `count` | Rows matching the query on the server, across every page |
| `pageNumber` / `pageSize` / `pageCount` | Position and size of the loaded page |
| `hasNext` / `hasPrevious` | Whether a page exists after or before this one |
| `loading` | `true` while a request is in flight |

## Event Listeners

Attach listeners to actions on the queryset or individual items:

```javascript
// Listen for saves on any item in the queryset
Glue.querySet.tasks.addListener('save', (event) => {
    console.log('Item saved:', event.result)
}, 'after')

// Listen for deletes
Glue.querySet.tasks.addListener('delete', (event) => {
    console.log('Item deleted')
}, 'after')
```

Child item events bubble up to the parent queryset's listeners automatically.

## Full Example: Task List with CRUD

### Backend

```python
from django.shortcuts import render
from django_glue import Glue, GlueAccess, ALL_FIELDS
from myapp.models import Task

def task_list_view(request):
    Glue.queryset(
        request=request,
        unique_name='tasks',
        target=Task.objects.all(),
        access=GlueAccess.DELETE,
        fields=ALL_FIELDS,
    )

    return render(request, 'tasks/list.html')
```

### Frontend

```html
{% load django_glue %}
<!DOCTYPE html>
<html>
<head>
    <title>Task List</title>
    <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3/dist/cdn.min.js"></script>
</head>
<body>
    <div x-data="{
        search: '',
        page: 1,
        get tasks() {
            return Glue.querySet.tasks
                .filter({title__icontains: this.search})
                .orderBy('-created_at')
                .page(this.page)
        },

        async addTask() {
            const task = await Glue.querySet.tasks.new({title: 'New Task'})
            await task.save()
            this.page = 1
        },
    }">
        <input x-model.debounce="search" @input="page = 1" placeholder="Search">
        <button @click="addTask()">Add Task</button>

        <template x-for="task in tasks.items" :key="task.$key">
            <div>
                <input x-model="task.title" placeholder="Task title">
                <label>
                    <input type="checkbox" x-model="task.done"> Done
                </label>
                <button @click="task.save()">Save</button>
                <button @click="task.delete()">Delete</button>
            </div>
        </template>

        <div>
            <button :disabled="!tasks.hasPrevious" @click="page -= 1">Previous</button>
            <span x-text="`Page ${tasks.pageNumber} of ${tasks.pageCount} (${tasks.count} tasks)`"></span>
            <button :disabled="!tasks.hasNext" @click="page += 1">Next</button>
        </div>
    </div>

    {% django_glue_init %}
</body>
</html>
```

## Access Levels

| Access Level | Available Actions |
|-------------|-------------------|
| `VIEW` | `query_with_params()`, `get()`, `new()`, `foreign_key_choices()` |
| `CHANGE` | All VIEW actions + child item `save()` |
| `DELETE` | All CHANGE actions + child item `delete()` |
