# Functions

Use `Glue.function()` for a Python callable imported by dotted path:

```python
Glue.function(
    request=request,
    unique_name='calculate_total',
    target='billing.calculations.calculate_total',
)
```

```javascript
const total = await Glue.function.calculate_total({hours: 4, rate: 125})
```

The callable's declared parameter names and allowed arguments are compiled
into its capability. The server validates a call against that signed
capability and the current declaration. Values are serialized through the
ordinary Glue value boundary.

A callable may return ordinary serializable data or a directly declared,
configured Glue object. An introduced object receives its own address and
policy; the client resolves the result to that canonical proxy. Raw Django
models, forms, and querysets are not automatically exposed from a result.

Function objects and custom `BaseGlue` objects can emit declared events.
Subscribe with the source proxy's `$on()`; see
[declared events](advanced/event_listeners.md).
