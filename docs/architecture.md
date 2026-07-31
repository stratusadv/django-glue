# Django Glue Architecture

This document describes the complete data flow through django-glue, from object registration to frontend proxy usage and attribute call resolution.

---

## 1. GlueObject Registration & Types

### Registry Mechanism

**File:** `django_glue/glue/registry.py`

The `GlueObjectResolverRegistry` maps namespace strings to BaseGlue subclasses:

```python
class GlueObjectResolverRegistry:
    def __init__(self) -> None:
        self.glue_object_classes: dict[str, type[BaseGlue]] = {}

    def register_glue_object_class(self, glue_object_class: type[BaseGlue]) -> None:
        self.glue_object_classes[glue_object_class.namespace] = glue_object_class

    def get_class_for_namespace(self, namespace: str) -> type[BaseGlue]:
        return self.glue_object_classes[namespace]
```

Each GlueObject subclass must define a class-level `namespace` attribute (e.g., `namespace = 'model'`). Built-in types are auto-registered via `_register_builtins()` on module load.

### Built-in GlueObject Types

| Type             | Namespace      | Wraps                 | Key Features                                                    |
| ---------------- | -------------- | --------------------- | --------------------------------------------------------------- |
| `ModelGlue`    | `'model'`    | Django Model instance | Field exposure, save/load/delete, FK handling, form integration |
| `FormGlue`     | `'form'`     | Django Form instance  | Field validation, save for ModelForms                           |
| `QuerySetGlue` | `'querySet'` | Django QuerySet       | filter/order/slice, returns child ModelGlue objects             |
| `FunctionGlue` | `'function'` | Python callable       | Execute with kwargs                                             |
| `TemplateGlue` | `'template'` | Django template path  | Render HTML with context                                        |

### BaseGlue Interface

**File:** `django_glue/glue/base.py`

All GlueObjects inherit from `BaseGlue`:

```python
class BaseGlue(ABC):
    namespace: str  # Must be overridden by each subclass

    @property
    @abstractmethod
    def identity(self) -> dict[str, Any]:
        """Object-specific data for reconstruction (pk, model path, etc.)"""

    @property
    def state(self) -> dict[str, Any]:
        """Mutable state from attributes."""

    @cached_property
    @abstractmethod
    def metadata(self) -> GlueMetadata:
        """Frontend schema for this object."""

    @classmethod
    @abstractmethod
    def _reconstruct_from_policy(cls, policy: GluePolicy) -> BaseGlue:
        """Reconstruct a GlueObject from a signed policy."""

    @cached_property
    def attributes(self) -> dict[str, BaseGlueAttribute]:
        """Runtime attributes exposed by this object."""
        return GlueAttributeCollector(self).collect()
```

---

## 2. Serialization & Frontend Delivery

### Flow: Server to Client

```
View Handler
    Glue.model(request, 'user', instance, access=...)
        │
        ▼
GlueContextManager.add_glue(glue)
    - Creates session if needed
    - Stores manifest in request.__dict__['__glue_manifest__']
        │
        ▼
GlueManifest = {
    policy: GluePolicy (signed),
    metadata: GlueMetadata
}
        │
        ▼
Template Tag: {% django_glue_init %}
    - Serializes all manifests to JSON
    - Injects into HTML via json_script filter
        │
        ▼
Frontend: GlueClient constructor
    - Parses JSON from <script> tag
    - Creates proxy getters for each manifest
```

### GlueContextManager

**File:** `django_glue/glue/context.py`

```python
class GlueContextManager:
    def __init__(self, request: HttpRequest):
        self.manifests = request.__dict__.setdefault('__glue_manifest__', [])

    def add_glue(self, glue: BaseGlue) -> None:
        if not self.request.session.session_key:
            self.request.session.create()

        glue.request = self.request
        self.manifests.append(glue.manifest)
```

### GluePolicy Structure

**File:** `django_glue/glue/policy.py`

```python
class GluePolicy(BaseModel):
    session_id: str              # Current session key
    request_user_id: Any         # Current user ID
    name: str                    # Unique identifier (e.g., "user")
    namespace: str               # Type namespace (e.g., "model")
    identity: dict[str, Any]     # Data for reconstruction
    access: GlueAccess           # Permission level
    attributes: list[str | Self] # Authorized attributes (or nested policies)
    created_at: float            # Timestamp
    original_signature: str      # HMAC-SHA256 signature
```

The policy is signed using Django's `SECRET_KEY`:

```python
@staticmethod
def _sign_data(data: dict) -> str:
    return hmac.digest(
        settings.SECRET_KEY.encode(),
        json.dumps(data, default=str, sort_keys=True).encode(),
        'sha256',
    ).hex()
```

### Template Tag

**File:** `django_glue/templatetags/django_glue.py`

```html
{% django_glue_init %}
```

Injects:

```javascript
const context = {
    manifest_list: [...],
    urls: {
        callable_attribute: '/__dg__/callable_attribute/',
    },
    config: { requestTimeoutSeconds: 30 }
}
window.Glue = new GlueClient(context)
```

---

## 3. Frontend Proxy System

### Proxy Class Hierarchy

```
BaseGlueProxy
├── FieldBackedGlueProxy
│   ├── GlueModelProxy      (namespace: 'model')
│   └── GlueFormProxy       (namespace: 'form')
├── GlueQuerySetProxy       (namespace: 'querySet')
├── GlueTemplateProxy       (namespace: 'template')
└── GlueFunctionProxy       (namespace: 'function')
```

### Proxy Registration

**File:** `client_js/src/client.js`

```javascript
window.Glue = {
    model: { user: <GlueModelProxy> },
    form: { contact: <GlueFormProxy> },
    querySet: { users: <GlueQuerySetProxy> },
    function: { myFunc: <GlueFunctionProxy> }
}
```

### Attribute Initialization

Each proxy initializes attributes based on policy and metadata:

1. **State attributes** - Getters/setters backed by `_state`
2. **Callable attributes** - Async methods that call backend
3. **Field attributes** - `$fields.name.value`, `.errors`, etc.
4. **Nested glue objects** - Recursive proxy creation

```javascript
// Callable attribute becomes async method
_initializeCallableAttribute(owner, attributeName, qualName, metadata) {
    Object.defineProperty(owner, attributeName, {
        value: async function(kwargs = {}) {
            return await root._callAttribute(qualName, kwargs)
        }
    })
}
```

---

## 4. Attribute Call Resolution

### Complete Round-Trip Flow

```
Frontend                                    Backend
────────                                    ───────
await user.save({})
    │
    ▼
_callAttribute('save', {})
    │
    ▼
HTTP POST /__dg__/callable_attribute/user/save/
    FormData: policy, state, attribute, kwargs
                                                │
                                                ▼
                                    glue_attribute_call_view()
                                                │
                                                ▼
                                    AttributeCallResolverContext.model_validate()
                                        - Validate content-type
                                        - Parse policy, state, kwargs
                                        - GluePolicy validates:
                                          * HMAC signature
                                          * Session match
                                          * User match
                                          * Not expired
                                                │
                                                ▼
                                    AttributeCallResolver.resolve()
                                                │
                                                ▼
                                    registry.get_class_for_namespace(policy.namespace)
                                        → ModelGlue
                                                │
                                                ▼
                                    ModelGlue._reconstruct_from_policy(policy)
                                        - Reconstruct model from identity['target_pk']
                                                │
                                                ▼
                                    glue_object._load_client_state(state)
                                                │
                                                ▼
                                    process_attribute_call(context)
                                        - Lookup attribute
                                        - Check access level
                                        - CallableAttribute.call(context)
                                                │
                                                ▼
                                    _resolve_call_parameters()
                                        - HttpRequest by type hint
                                        - kwargs from context
                                                │
                                                ▼
                                    Execute: save(request=<HttpRequest>)
                                                │
                                                ▼
                                    Response: {
                                        data: {state, policy, metadata, result, messages},
                                        status: 200
                                    }
    │
    ▼
_applyResponse(data)
    - Update policy (re-signed)
    - Deep merge state
    - Process messages
    │
    ▼
return result
```

### Policy Validation

**File:** `django_glue/glue/schemas.py`

1. Verify content-type is `multipart/form-data`
2. Parse policy, state, kwargs from JSON
3. Validate policy name matches URL path
4. Verify session_id matches current session
5. Verify request_user_id matches current user
6. Verify HMAC signature
7. Check policy not expired

### Object Reconstruction

Each GlueObject type implements `_reconstruct_from_policy()`:

```python
# ModelGlue example
@classmethod
def _reconstruct_from_policy(cls, policy: GluePolicy) -> ModelGlue:
    model_class = get_attr_from_path_string(policy.identity['model_class_path'])
    instance = model_class.objects.get(pk=policy.identity['target_pk'])
    return cls(instance, name=policy.name, access=policy.access, ...)
```

### Parameter Resolution

**File:** `django_glue/glue/attributes/callable.py`

```python
def _resolve_call_parameter(self, param_name, param, type_hint, context):
    call_parameters = context.target_attribute_call_kwargs

    # 1. Client-provided value takes priority
    if param_name in call_parameters:
        return call_parameters[param_name]

    # 2. Inject HttpRequest by type hint
    if type_hint and issubclass(type_hint, HttpRequest):
        return context.request

    # 3. Use default if available
    if param.default is not inspect.Parameter.empty:
        return None  # Let Python use default

    # 4. Error for missing required parameter
    raise ValueError(f"Missing required argument: '{param_name}'")
```

---

## 5. Security Model

### HMAC-SHA256 Signatures

- Policy signed with Django's `SECRET_KEY`
- Signature verified on every attribute call
- Detects tampering with access level, attributes, identity

### Session Binding

- `policy.session_id` must match `request.session.session_key`
- Prevents cross-session policy reuse

### User Binding

- `policy.request_user_id` must match `request.user.id`
- Prevents cross-user policy reuse

### Expiration

- `policy.created_at` timestamp checked against max age
- Default: 3600 seconds (1 hour)
- Configurable via `DJANGO_GLUE_PROXY_POLICY_MAX_AGE_SECONDS`

### Access Level Hierarchy

```
VIEW < CHANGE < DELETE < CREATE
```

Attribute calls check: `policy.access >= attribute.required_access`

### Attribute Whitelisting

- Only attributes listed in `policy.attributes` can be called
- Server validates attribute name against policy

### CSRF Protection

- All POST requests include CSRF token
- Standard Django CSRF middleware applies

---

## 6. Attributes vs GlueObjects

Understanding the distinction between these two concepts is key to understanding the architecture.

### What They Are

| Concept | GlueObject (`BaseGlue`) | Attribute (`BaseGlueAttribute`) |
|---------|-------------------------|--------------------------------|
| **Purpose** | Wraps a domain object (model, form, queryset, function) and makes it remotely accessible | Represents a single access point on a GlueObject |
| **Examples** | `ModelGlue`, `FormGlue`, `QuerySetGlue`, `FunctionGlue` | `ModelFieldAttribute`, `CallableAttribute`, `GlueObjectAttribute` |
| **Has Policy** | Yes - signed, authoritative | No - permissions come from owner |
| **Has Metadata** | Yes - client-side schema | Yes - per-attribute schema |
| **Has State** | Yes - aggregates attribute states | Some do (field values, errors) |
| **Is Callable** | Not directly | `CallableAttribute` is |

### The Fundamental Difference

**GlueObjects are the unit of authorization.** They have:
- A signed `GluePolicy` with HMAC verification
- An `identity` (how to reconstruct from policy)
- An `access` level that gates what operations are permitted

**Attributes are the unit of interaction.** They have:
- A `required_access` level (checked against owner's policy)
- Either `state` (readable data) or `call()` (invocable method)

Think of it as: **GlueObjects are nouns** (things you can access), **Attributes are verbs/adjectives** (what you can do/read on them).

### Attribute Types

Attributes normalize different data sources into a uniform interface:

| Attribute Type | Source | Provides |
|---------------|--------|----------|
| `ModelFieldAttribute` | `Model.field` | state (value + errors) |
| `FormFieldAttribute` | `Form.fields[name]` | state (value + errors + widget metadata) |
| `CallableAttribute` | method with `@DeclaredAttribute` | invocable call |
| `ReadableAttribute` | any attribute | state (value only) |
| `GlueObjectAttribute` | nested `BaseGlue` | state + nested metadata |
| `ForeignKeyFieldAttribute` | FK field + related model | state + nested glue for navigation |

### The Bridge: GlueObjectAttribute

`GlueObjectAttribute` embeds one GlueObject inside another as an attribute:

```python
class GlueObjectAttribute(BaseGlueAttribute):
    def __init__(self, ..., glue_object: BaseGlue):
        self.glue_object = glue_object

    @property
    def state(self) -> dict[str, Any]:
        return self._prepare_glue_object().state
```

This is used for:
- **Form embedding**: `ModelGlue` exposes `FormGlue` via `forms.default` attribute
- **FK relationships**: `ForeignKeyFieldAttribute` creates nested `ModelGlue` for related objects

The nested GlueObject's metadata is included in the parent's metadata, enabling frontend proxy creation for the entire object graph.

### Attribute Collection

**File:** `django_glue/glue/attributes/collector.py`

The `GlueAttributeCollector` discovers attributes from multiple sources:

1. **Declared attributes** - Methods decorated with `@DeclaredAttribute` on the GlueObject class
2. **Provider attributes** - `@DeclaredAttribute` methods on objects returned by `attribute_providers`
3. **Field attributes** - Created programmatically (e.g., `ModelFieldAttribute` for each model field)

```python
class GlueAttributeCollector:
    def collect(self) -> dict[str, BaseGlueAttribute]:
        attributes = {}
        # 1. Collect from GlueObject class
        attributes.update(self._collect_declared_attributes(self.glue_object))
        # 2. Collect from attribute providers
        for provider in self.glue_object.attribute_providers.values():
            attributes.update(self._collect_declared_attributes(provider))
        return attributes
```

Field attributes (model fields, form fields) are added by the GlueObject subclass in its `attributes` property override.

---

## 7. Composition Patterns

### Nested GlueObjects

`GlueObjectAttribute` wraps nested glue objects:

```python
# ModelGlue with nested FormGlue
ModelGlue(instance, forms={'edit': UserEditForm})
    ├── ModelFieldAttribute('name')
    ├── ModelFieldAttribute('email')
    ├── GlueObjectAttribute('forms.edit')
    │       └── FormGlue(UserEditForm)
    │           ├── FormFieldAttribute('name')
    │           └── FormFieldAttribute('email')
    ├── CallableAttribute('save')
    └── CallableAttribute('delete')
```

Policy contains nested policies with their own signatures:

```python
attributes: [
    'name',
    'email',
    GluePolicy(name='forms.edit', namespace='form', ...),
    'save',
    'delete'
]
```

### Attribute Providers

The `attribute_providers` property returns objects whose `@DeclaredAttribute`-decorated members are exposed through the parent GlueObject:

```python
@property
def attribute_providers(self) -> dict[str, Any]:
    return {'services': self.task_service}
```

### ForeignKey Relationships

`ForeignKeyFieldAttribute` wraps related objects as nested ModelGlue:

```python
# Accessing user.profile (FK relationship)
user.$fields.profile.value  # Returns nested ModelGlue proxy
```

---

## 8. Key Files Reference

| Area                  | File                                        | Purpose                                         |
| --------------------- | ------------------------------------------- | ----------------------------------------------- |
| **Entry point** | `shortcuts/glue.py`                       | `Glue.model()`, `Glue.form()`, etc.         |
| **Context**     | `glue/context.py`                         | GlueContextManager, manifest storage            |
| **Base**        | `glue/base.py`                            | BaseGlue, process_attribute_call                |
| **Policy**      | `glue/policy.py`                          | GluePolicy, HMAC signing                        |
| **Registry**    | `glue/registry.py`                        | Namespace → class mapping                      |
| **Attributes**  | `glue/attributes/`                        | BaseGlueAttribute, CallableAttribute, collector |
| **Model**       | `glue/objects/django/model/object.py`     | ModelGlue                                       |
| **Form**        | `glue/objects/django/form/object.py`      | FormGlue                                        |
| **QuerySet**    | `glue/objects/django/queryset.py`         | QuerySetGlue                                    |
| **Resolver**    | `resolver/callable_attribute/resolver.py` | AttributeCallResolver                           |
| **Schemas**     | `glue/schemas.py`                         | AttributeCallResolverContext                    |
| **View**        | `glue/views.py`                           | glue_attribute_call_view                        |
| **Templates**   | `templatetags/django_glue.py`             | `{% django_glue_init %}`                      |
| **JS Client**   | `client_js/src/`                          | GlueClient, proxies, HTTP                       |
