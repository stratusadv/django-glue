# Function Proxy Guide

## Purpose

Function proxies allow you to call Python functions from JavaScript with keyword arguments arguments. You register a function by its dotted import path, and the proxy automatically extracts its signature so the client knows what parameters to pass.

### When to Use

- When you need to call a Python utility function from the frontend without writing a custom API endpoint.
- When you want to run server-side computation (e.g., calculations, lookups, data transformations) triggered by user actions.
- When you need to expose a callable that takes arguments and returns a result.

### When Not to Use

- When the function needs to perform CRUD operations on a model. Use a [Model proxy](model_object_glue.md) instead.
- When the function needs to render HTML. Use a [Template proxy](template_glue.md) or [GlueView](view_glue/view_glue.md) instead.
- When the function is a bound method on an instance. Function proxies only support standalone functions identified by dotted path.

## Backend: Registering a Function Proxy

Use `Glue.function()` in your Django view to register a function:

```python
from django_glue import Glue, GlueAccess

def my_view(request):
    Glue.function(
        request=request,
         unique_name='calculate_total',
        target='myapp.utils.calculate_total',
        access=GlueAccess.VIEW,
    )

    return render(request, 'my_view.html')
```

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `request` | `HttpRequest` | Yes | The current request |
| `unique_name` | `str` | Yes | Unique identifier for the proxy in the session |
| `target` | `str` | Yes | Dotted import path to the function (e.g., `'myapp.utils.my_func'`) |
| `access` | `GlueAccess` | No | Access level (default: `VIEW`) |

### How It Works

The function is identified by its dotted import path string. On each action request, the server resolves the path using `importlib` to get the callable. The function's signature is extracted using `inspect.signature()` and sent to the client in the context data, so the JavaScript side knows the parameter names and types.

```python
# myapp/utils.py
def calculate_total(amount: float, tax_rate: float, include_discount: bool) -> float:
    total = amount * (1 + tax_rate)
    if include_discount:
        total *= 0.9
    return round(total, 2)
```

## Frontend: Using the Function Proxy

Access the proxy as a callable property of the global `Glue.function` object using the unique name you provided:

```javascript
// If you registered with unique_name='calculate_total':
const result = await Glue.function.calculate_total(100, 0.08, true)
// Returns: 97.2
```

### Signature-Matching Calls

Keyword arguments are mapped to the function's parameter names via object fields:

```javascript
// Python: greet(name, greeting='Hello')
const msg = await Glue.function.greet({subject: 'World'})
// Returns: 'Hello, World!'

// Override the default greeting
const msg = await Glue.function.greet({subject: 'World', message: 'Hi'})
// Returns: 'Hi, World!'
```

### Parameter Metadata

The function's parameters are available on the callable for inspection:

```javascript
// Access parameter definitions
const params = Glue.function.calculate_total._params
// [
//   { name: 'amount', type: 'float' },
//   { name: 'tax_rate', type: 'float' },
//   { name: 'include_discount', type: 'bool' }
// ]
```

## Event Listeners

Function proxies support the same listener system as other proxies. Attach listeners to the `'execute'` action:

```javascript
// Before call
Glue.function.calculate_total.addListener('execute', (event) => {
    console.log('Calling with:', event.payload)
}, 'before')

// After call
Glue.function.calculate_total.addListener('execute', (event) => {
    console.log('Result:', event.result)
}, 'after')

// On error
Glue.function.calculate_total.addListener('execute', (event) => {
    console.error('Call failed:', event.error)
}, 'error')
```

## Full Example: Price Calculator

### Backend — Utility Function

```python
# myapp/utils.py
def calculate_price(base_price, quantity, discount_percent=0):
    subtotal = base_price * quantity
    discount = subtotal * (discount_percent / 100)
    return {
        'subtotal': round(subtotal, 2),
        'discount': round(discount, 2),
        'total': round(subtotal - discount, 2),
    }
```

### Backend — View

```python
from django.shortcuts import render
from django_glue import Glue, GlueAccess

def cart_view(request):
    Glue.function(
        request=request,
         unique_name='calculate_price',
        target='myapp.utils.calculate_price',
        access=GlueAccess.VIEW,
    )

    return render(request, 'cart.html')
```

### Frontend

```html
{% load django_glue %}
<!DOCTYPE html>
<html>
<head>
    <title>Cart Calculator</title>
    <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3/dist/cdn.min.js"></script>
</head>
<body>
    <div x-data="{
        basePrice: 29.99,
        quantity: 1,
        discount: 10,
        result: null,

        async calculate() {
            this.result = await Glue.function.calculate_price(
                this.basePrice,
                this.quantity,
                this.discount
            )
        }
    }" @submit.prevent="calculate()">
        <h2>Price Calculator</h2>

        <label>Base Price: <input type="number" x-model.number="basePrice" step="0.01"></label><br>
        <label>Quantity: <input type="number" x-model.number="quantity"></label><br>
        <label>Discount %: <input type="number" x-model.number="discount"></label><br>

        <button type="submit">Calculate</button>

        <template x-if="result">
            <div>
                <p>Subtotal: $<span x-text="result.subtotal"></span></p>
                <p>Discount: $<span x-text="result.discount"></span></p>
                <p><strong>Total: $<span x-text="result.total"></span></strong></p>
            </div>
        </template>
    </div>

    {% django_glue_init %}
</body>
</html>
```

## Access Levels

| Access Level | Available Actions |
|-------------|-------------------|
| `VIEW` | `execute()` |
| `CHANGE` | All VIEW actions |
| `DELETE` | All VIEW actions |

Function proxies default to `VIEW` access, as calling a function is considered a read-only operation. Use `CHANGE` or `DELETE` if the function performs side effects that modify state.

## Function Proxy vs Model Proxy Actions

| Feature | `Glue.function`                  | `Glue.model` actions |
|---------|----------------------------------|---------------------|
| Target | Any callable function            | Django model instance |
| Parameters | Keyword args mapped by signature | Field data via `action_kwargs` |
| Validation | No built-in validation           | Django ModelForm validation |
| Return value | Function's return value          | Action-specific result dict |
| Use case | Arbitrary server-side computation | CRUD operations on models |

Use `Glue.function` for general-purpose server-side calls. Use model proxy actions (`save()`, `delete()`, etc.) when working with Django models.
