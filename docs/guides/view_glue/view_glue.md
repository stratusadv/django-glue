# Render a Django view into a page

`Glue.view(url)` fetches HTML from the actual Django route. The route's
middleware, decorators, and view authorization run as for a normal request.
`GlueViewMiddleware`, last in `MIDDLEWARE`, packages a successful HTML
response with objects introduced during that render.

```javascript
const view = Glue.view('/tasks/panel/')
await view.renderInnerHtml(document.getElementById('panel'))
```

`renderInnerHtml` morphs the target's children and accepts empty or
multi-root HTML. `renderOuterHtml` morphs the target element and requires
exactly one root element. `renderInsertAdjacentHtmlBeforeEnd`,
`renderInsertAdjacentHtmlAfterEnd`, `renderInsertAdjacentHtmlBeforeBegin`,
and `renderInsertAdjacentHtmlAfterBegin` insert adjacent HTML. Render methods
return the HTML string.

`get(payload)` sends a GET request with query parameters. `post(payload)`
sends a JSON POST. Render methods use POST. A second argument to
`Glue.view(url, sharedPayload)` supplies values merged into every request.

```javascript
const view = Glue.view('/tasks/panel/', {team: 42})
const html = await view.get({status: 'open'})
await view.renderOuterHtml(document.getElementById('panel'), {status: 'open'})
```

Glue registers the response's addressed entries before morphing, so an
inserted component can resolve its proxy. Matching keyed nodes preserve
Alpine state, focus, and local input state. Use stable keys for repeated
elements, and `data-morph-ignore` for a third-party widget subtree that
should stay untouched while its root remains in the page.
