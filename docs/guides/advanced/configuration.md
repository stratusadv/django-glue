# Configuration

Set `DJANGO_GLUE_*` values in Django settings. The defaults live in
`django_glue/settings.py`.

| Setting | Default | Purpose |
| --- | ---: | --- |
| `DJANGO_GLUE_PROXY_POLICY_MAX_AGE_SECONDS` | `86400` | Fixed lifetime from token issuance |
| `DJANGO_GLUE_REQUEST_TIMEOUT_SECONDS` | `30` | Browser request timeout |
| `DJANGO_GLUE_QUERYSET_BATCH_SIZE` | `100` | Default rows returned per queryset query |
| `DJANGO_GLUE_MAX_UPDATES` | `200` | Editable paths in one addressed request |
| `DJANGO_GLUE_MAX_UPDATES_ENCODED_BYTES` | `65536` | Encoded update payload size |
| `DJANGO_GLUE_MAX_POLICY_TOKEN_BYTES` | `131072` | Token size before signature verification |
| `DJANGO_GLUE_MAX_POLICY_DECODED_BYTES` | `131072` | Decoded token size before parsing |
| `DJANGO_GLUE_MAX_QUERY_ENCODED_BYTES` | `65536` | Encoded queryset continuation size |

A successor policy token gets a new issuance time only when retained values
change. An expired child may be reintroduced through its owner; an expired
page root requires a reload.

`DJANGO_GLUE_QUERYSET_BATCH_SIZE` controls query results, not introduction:
querysets introduce no rows until queried. A `Glue.choices()` queryset with
`search_fields` returns bounded matches for a query. Implicit relation choices
are capped and require an explicit choice source when the related table is
larger than the default search limit.

The JavaScript client sends CSRF tokens on POST requests. Include
`django_glue_urls()` for `POST /__dg__/callable_attribute/` and put
`django_glue.middleware.GlueViewMiddleware` last in `MIDDLEWARE` for
`Glue.view(url)`. That view API requests the actual Django URL.
