# Django Glue Codewalk Notes

## `conf.py` - Settings Proxy Pattern
- Return type is `Any` - loses type safety. Could use `@overload` for known settings.
- No caching - every attribute access does two `hasattr` + `getattr` calls. For hot paths, this adds overhead.

## `access.py` - Permission Hierarchy

```python
def has_access(self, access_required: GlueAccess) -> bool:
    access_tuple = tuple(GlueAccess.__members__.values())
    return access_tuple.index(self) >= access_tuple.index(access_required)
```

**Issues:**
1. **Performance**: Creates a tuple and does two linear scans (`index()`) on every call. For an access check that likely happens frequently, this is wasteful. Could precompute ordinals.
2. **Fragile**: Relies on declaration order as the hierarchy. A future developer could reorder the enum members and silently break security. The comment warns about this, but comments aren't enforced.
3. **Semantic confusion**: `has_access(access_required)` reads as "do I have the required access?" but the logic is "is my permission level >= required level". The name `has_access` on an enum value is odd - typically you'd have `can_perform(action)` or similar.

## `response.py`

1. **`GlueRedirectResponse` using `__new__`** - This is unusual. It's a factory that returns a `GlueResponse`, not a subclass. Why not just make it a function? Using `__new__` this way means `isinstance(x, GlueRedirectResponse)` will always be `False`. Misleading API.
2. **`Message: ClassVar[type]`** - Attached to the dataclass for... convenience? This couples the message type to the response class in a way that's not obviously useful.
3. **`messages: Iterable[GlueMessage] | None = None`** then immediately converted to list in `__post_init__`. Why accept `Iterable` if you're just going to listify it? Could type it as `list[GlueMessage] | None` and use `field(default_factory=list)`.

## `shortcuts/glue.py` - Glue Facade

1. **`function()` takes `target: str`** - Dotted path string, defers import. Security consideration: who validates this path?

## `glue/context.py` - GlueContextManager

1. **URL hardcoding** - `_glue_client_context` builds URLs with string concatenation instead of `reverse()`. If django-glue is mounted at a different prefix, this breaks.

## `glue/attributes/` - Attribute System (Refactored)

### Changes Made

1. **Extracted `GlueAttributeCollector`** - Moved attribute discovery logic from `BaseGlue._discover_attributes` to `glue/attributes/collector.py`. ~140 lines of discovery code now lives in a dedicated class.

2. **Centralized attribute options** - Created `DeclaredAttributeOptions` dataclass in `declared.py`:
   ```python
   @dataclass(frozen=True)
   class DeclaredAttributeOptions:
       access: GlueAccess
       is_callable: bool = True
       loads_state: bool = True
   ```
   Replaces scattered dunders (`__required_glue_access__`, `is_callable`, `loads_state`). Now exposed as single `__glue_options__` attribute.

3. **Renamed `Attribute` to `DeclaredAttribute`** - Distinguishes the decorator/descriptor from runtime `BaseGlueAttribute` instances.

4. **Renamed `target` to `attr_owner_instance`** - In all attribute classes. Clarifies that this is the instance from which to resolve the attribute value, not the callable/property target.

5. **Depth-first recursion** - Changed from breadth-first to depth-first when collecting nested container attributes. Cleaner tree resolution.

6. **Removed silent exception swallowing** - `_resolve_attribute_value` (now removed) had a try/except that silently skipped attributes on error. Errors now propagate.

### Remaining Issues

1. **`callable.py` line 73 TODO** - "this is not the thing to raise" comment indicates wrong exception type.

2. **`callable.py` line 125-126** - Questionable logic: if parameter not in resolved_kwargs and has no default, we `continue` without error. Should this raise for required parameters?

3. **`callable.py` `_resolve_call_kwargs`** - Method is doing a lot (signature inspection, type hint injection, convention-based kwargs). Consider breaking down.
