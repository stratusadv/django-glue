# Plan: Replace `action_providers` with `attributes`

## Goal

Remove the `action_providers` attribute from `GlueMeta` and its processing pipeline. Replace it with `attributes`, which register model methods as custom Glue actions exposed on frontend proxy objects.

## Key Design Decisions

- **Attributes** are declared in `GlueMeta.attributes` as `[('method_name', GlueAccess)]` tuples
- No `@action` decorator needed on the model method
- Methods do **not** receive `request: HttpRequest` — they are simpler
- Methods **do** support keyword arguments from the client
- Execution: `getattr(target_instance, attr_name)(**kwargs)` — no callable lookup, just direct getattr
- `GorillaService.py` is deleted (dead code)

---

## File Changes

### 1. `django_glue/actions/action.py`

#### Change `GlueAction` model

**Remove:**
- `provider_class_path: str`
- `client_proxy_access_path: str = ''`
- `provider_factory: Callable | None = None`
- `provider_class` property
- `callable` property's `provider_class` branch

**Add:**
- `is_attribute: bool = False`

**Updated model:**
```python
class GlueAction(BaseModel):
    name: str
    parameters: dict[str, str | None]
    required_access: GlueAccess
    target_class_path: str
    is_attribute: bool = False

    @property
    def target_class(self) -> type:
        target_class = get_attr_from_path_string(self.target_class_path)
        if not isinstance(target_class, type):
            raise ValueError('target_class_path for instance does not refer to a valid class.')
        return target_class

    @property
    def callable(self) -> Callable:
        target_class = self.target_class
        action_function = getattr(target_class, self.name, None)
        if not action_function or not isinstance(action_function, Callable):
            raise ValueError(f'Could not find valid callable named {self.name} on action target class {target_class.__name__}')
        return action_function
```

#### Change `register_target_actions`

**Remove** the `action_providers` loop (lines 60-72):
```python
# REMOVE THIS BLOCK:
glue_options = getattr(target, 'GlueMeta', None)
if glue_options:
    for action_provider_class, action_provider_config in getattr(
        glue_options,
        'action_providers', None
    ) or []:
        if action_provider_class.__name__ not in GLUE_ACTIONS:
            register_action_provider(...)
```

**Replace with** `attributes` loop:
```python
glue_options = getattr(target, 'GlueMeta', None)
if glue_options:
    for attr_name, required_access in getattr(glue_options, 'attributes', None) or []:
        key_name = f'{target.__class__.__name__}.{attr_name}'
        if key_name in GLUE_ACTIONS:
            continue

        method = getattr(target.__class__, attr_name, None)
        if not method or not callable(method):
            continue

        signature = inspect.signature(inspect.unwrap(method))
        parameters = signature.parameters
        parameter_data: dict[str, str | None] = {}

        # Skip 'self' parameter — attributes don't take request
        for param_name, param_value in list(parameters.items())[1:]:
            annotation = param_value.annotation
            if annotation is inspect.Parameter.empty:
                parameter_data[param_name] = None
            elif isinstance(annotation, type):
                parameter_data[param_name] = annotation.__name__
            else:
                parameter_data[param_name] = str(annotation)

        GLUE_ACTIONS.update({
            key_name: GlueAction(
                name=attr_name,
                parameters=parameter_data,
                required_access=required_access,
                target_class_path=f'{target.__class__.__module__}.{target.__class__.__name__}',
                is_attribute=True,
            ),
        })
```

#### Change `register_action_provider`

**Remove** `client_proxy_access_path` and `provider_factory` parameters:
```python
def register_action_provider(
        action_provider_class: type,
        target_class: type,
    ) -> None:
```

**Remove** `client_proxy_access_path` and `provider_factory` from the `GlueAction` constructor call inside (lines 107-117).

**Update** the loop to skip `self` (index 1 instead of 2) since attributes don't take `request`:
```python
for param_name, param_value in list(parameters.items())[1:]:
```

Wait — `register_action_provider` is still used for `@action` decorated methods on proxy classes and provider classes. The `[2:]` skip is correct there (skips `self` and `request`). Only the new `attributes` loop skips 1 (just `self`).

So `register_action_provider` stays as-is except for removing the two parameters. The parameter loop stays at `[2:]`.

### 2. `django_glue/proxies/proxy.py`

#### In `process_action_request` (lines 180-217)

**Remove** the `provider_factory` block (lines 200-203):
```python
# REMOVE:
if action.provider_factory is not None:
    action_target = action.provider_factory(action_target)
```

**Add** attribute handling — for attributes, skip `_build_action_kwargs` (which expects `request` param) and call directly:
```python
if action.is_attribute:
    # Attributes: simple getattr call with kwargs, no request injection
    action_callable = getattr(action_target, action.name)
    action_kwargs = action_request.action_kwargs or {}
    action_result_data = action_callable(**action_kwargs)
else:
    action_callable = action.callable
    action_kwargs = instance._build_action_kwargs(
        action_callable=action_callable,
        action_request=action_request,
    )
    action_result_data = action_callable(action_target, **action_kwargs)
```

#### In `_action_contract_data` (line 113)

Remove `provider_factory` from exclude set (since it no longer exists):
```python
action.model_dump(exclude_none=True)
```

### 3. `django_glue/actions/decorators.py`

**Remove** the `action_provider` decorator entirely (lines 26-45):
```python
# REMOVE:
def action_provider(
        target_class: type | None = None,
        access_path: str = '',
        provider_factory: Callable | None = None,
    ) -> Callable[..., Callable[..., type]]:
    ...
```

### 4. `django_glue/shortcuts/glue.py`

**Remove** `action_provider` import (line 9) and static method (line 15):
```python
# REMOVE from imports:
from django_glue.actions.decorators import action, action_provider
# CHANGE TO:
from django_glue.actions.decorators import action

# REMOVE from Glue class:
action_provider = staticmethod(action_provider)
```

### 5. `client_js/src/proxies/base.js`

#### In `_defineDefaultActions` (lines 162-191)

**Simplify** — remove `client_proxy_access_path` nesting logic since it no longer exists:
```javascript
_defineDefaultActions() {
    Object.entries(this._actions).forEach(([actionKey, action]) => {
        // actionKey is "ClassName.methodName", extract just the method name
        const actionName = actionKey.split('.').pop()

        if (!(actionName in this)) {
            Object.defineProperty(this, actionName, {
                get: function () {
                    return async (actionKwargs = null) => {
                        return await this._processAttributeEvent(actionKey, actionKwargs);
                    };
                },
                enumerable: true,
                configurable: true
            });
        }
    });
}
```

Also remove the `debugger` statement on line 182.

### 6. `test_project/gorilla/models.py`

**Remove** `action_providers` from `GlueMeta` (lines 103-110):
```python
# REMOVE:
action_providers = [
    (
        GorillaService,
        {
            'client_proxy_access_path': 'services.processor',
            'provider_factory': lambda g: GorillaService(g)
        }
    )
]
```

**Remove** `GorillaService` import at top of file:
```python
# REMOVE:
from test_project.gorilla.gorilla_service import GorillaService
```

### 7. `test_project/gorilla/gorilla_service.py`

**Delete the entire file.**

---

## Summary of Impact

| Concern | Status |
|---------|--------|
| `@action` decorated methods on proxy classes | Still work — `register_action_provider` still called for proxy classes |
| `@action` decorated methods on model classes (like `battle_cry`) | Still work — `register_target_actions(proxy)` registers proxy actions, `register_target_actions(target)` processes GlueMeta |
| `GlueAction` backward compat | `provider_class_path` removed — no existing code uses it outside the pipeline being removed |
| JS `client_proxy_access_path` nesting | Removed — actions now always appear directly on the proxy |
| `GorillaService` | Deleted — was only used by `action_providers` |

## Test Plan

1. Run `just run-tests` — verify Python tests pass
2. Run `just js-build` then `just js-tests` — verify JS tests pass
3. Manually test `battle_cry` action still works (uses `@action` decorator, not attributes)
4. Test a new `attributes` entry works end-to-end
