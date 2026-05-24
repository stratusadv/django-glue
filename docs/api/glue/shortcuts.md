# Glue API

The `Glue` class is the central entry point for registering proxies in your Django views. Import it with:

```python
from django_glue import Glue, GlueAccess
```

## Methods

| Method | Proxy Type | Wraps |
|--------|------------|-------|
| `Glue.model()` | `GlueModelProxy` | Single Django model instance |
| `Glue.queryset()` | `GlueQuerySetProxy` | Django QuerySet collection |
| `Glue.form()` | `GlueModelProxy` or `GlueFormProxy` | Django ModelForm or regular Form |

## Source

::: django_glue.Glue
